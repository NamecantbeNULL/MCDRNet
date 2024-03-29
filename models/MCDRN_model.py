import torch
import itertools
from .base_model import BaseModel
from . import networks
from . import vgg
import torch.nn.functional as F
import numpy as np
import skimage.measure as measure
import code
import torchvision.transforms as transforms


class MCDRNModel(BaseModel, torch.nn.Module):
    """
    This class implements the CycleGAN model, for learning image-to-image translation without paired data.

    The model training requires '--dataset_mode unaligned' dataset.
    By default, it uses a '--netG resnet_9blocks' ResNet generator,
    a '--netD basic' discriminator (PatchGAN introduced by pix2pix),
    and a least-square GANs objective ('--gan_mode lsgan').

    CycleGAN paper: https://arxiv.org/pdf/1703.10593.pdf
    """
    @staticmethod
    def modify_commandline_options(parser, is_train=True):
        """Add new dataset-specific options, and rewrite default values for existing options.

        Parameters:
            parser          -- original option parser
            is_train (bool) -- whether training phase or test phase. You can use this flag to add training-specific or test-specific options.

        Returns:
            the modified parser.

        For CycleGAN, in addition to GAN losses, we introduce lambda_A, lambda_B, and lambda_identity for the following losses.
        A (source domain), B (target domain).
        Generators: G_A: A -> B; G_B: B -> A.
        Discriminators: D_A: G_A(A) vs. B; D_B: G_B(B) vs. A.
        Forward cycle loss:  lambda_A * ||G_B(G_A(A)) - A|| (Eqn. (2) in the paper)
        Backward cycle loss: lambda_B * ||G_A(G_B(B)) - B|| (Eqn. (2) in the paper)
        Identity loss (optional): lambda_identity * (||G_A(B) - B|| * lambda_B + ||G_B(A) - A|| * lambda_A) (Sec 5.2 "Photo generation from paintings" in the paper)
        Dropout is not used in the original CycleGAN paper.
        """
        parser.set_defaults(no_dropout=False)  # default CycleGAN did not use dropout
        parser.add_argument('--blurKernel', type=int, default=5, help='maximum R for gaussian kernel')

        return parser

    def __init__(self, opt):
        """Initialize the CycleGAN class.

        Parameters:
            opt (Option class)-- stores all the experiment flags; needs to be a subclass of BaseOptions
        """
        BaseModel.__init__(self, opt)
        torch.nn.Module.__init__(self)
        self.loss_names = ['idt_T', 'res', 'MP', 'G', 'T', 'idt_T_curv', 'T_curv']

        if self.isTrain:
            self.visual_names = ['fake_Ts', 'real_T', 'fake_T_curvs', 'real_T_curv']
        else:
            self.visual_names = ['fake_Ts', 'real_T', 'real_I', 'fake_T_curvs', 'real_T_curv', 'real_I_curv']

        if self.isTrain:
            self.model_names = ['G_T', 'D']
        else:  # during test time, only load Gs
            self.model_names = ['G_T']

        self.vgg = vgg.Vgg19(requires_grad=False).to(self.device)
        # Define generator of synthesis net
        self.netG_T = networks.define_G(opt.input_nc, opt.input_nc, opt.ngf, opt.netG, opt.norm,
                                        not opt.no_dropout, opt.init_type, opt.init_gain, self.gpu_ids)
        self.netD = networks.define_D(opt.input_nc, opt.ndf, opt.netD, opt.n_layers_D, opt.norm, opt.init_type,
                                      opt.init_gain, self.gpu_ids)

        if self.isTrain:
            # torch.nn.utils.clip_grad_norm_(self.netG_T.parameters(), 0.25)
            # torch.nn.utils.clip_grad_norm_(self.netG_R.parameters(), 0.25)
            self.criterionGAN = networks.GANLoss(opt.gan_mode).to(self.device)
            self.criterionGradient = torch.nn.L1Loss()

            self.criterionVgg = networks.VGGLoss1(self.device, vgg=self.vgg, normalize=False)

            self.optimizer_G = torch.optim.Adam(itertools.chain(self.netG_T.parameters()),
                                                lr=opt.lr, betas=(opt.beta1, 0.999))
            self.optimizer_D = torch.optim.Adam(itertools.chain(self.netD.parameters()),
                                                lr=opt.lr, betas=(opt.beta1, 0.999))
            self.optimizers.append(self.optimizer_G)
            self.optimizers.append(self.optimizer_D)

        self.criterionIdt = torch.nn.MSELoss()

        resSize = 64
        self.k_sz = np.linspace(opt.batch_size, self.opt.blurKernel, 80)  # for synthetic images

        self.fake_T = torch.zeros(self.opt.batch_size, 3, 256, 256).to(self.device)
        self.fake_Ts = [self.fake_T]
        self.fake_T_curv = torch.zeros(self.opt.batch_size, 1, 256, 256).to(self.device)
        self.fake_T_curvs = [self.fake_T_curv]

        # Pass invalid data
        self.trainFlag = True

        ''' We use both real-world data and synthetic data. If 'self.isNatural' is True, the data loaded is real-world
        image paris. Otherwise, we use 'self.syn' to synthesize data.'''
        self.isNatural = False
        self.syn = networks.SynData(self.device)
        self.load_curv = networks.CurvMap()
        self.real_I = None
        self.real_I_curv = None
        self.real_T = None
        self.real_R = None
        self.real_T_curv = None
        # self.real_T2 = None
        # self.real_T2_LBP = None
        # self.real_T4 = None
        # self.real_T4_LBP = None
        self.alpha = None

    def set_input(self, input):
        """Unpack input data from the dataloader, perform necessary pre-processing steps and synthesize data.

        Parameters:
            input (dict): include the data itself and its metadata information.

        """
        with torch.no_grad():
            if self.isTrain:
                if input['isNatural'][0] == 1:
                    self.isNatural = True
                else:
                    self.isNatural = False
                # self.real_T2 = input['T2'].to(self.device)
                # self.real_T4 = input['T4'].to(self.device)
                if not self.isNatural:  # Skip these procedures, if the data is from real-world.
                    T = input['T'].to(self.device)
                    R = input['R'].to(self.device)
                    if torch.mean(T) * 1 / 2 > torch.mean(R):
                        self.trainFlag = False
                        return
                    _, R, I, alpha = self.syn(T, R, self.k_sz)  # Synthesize data
                    self.alpha = round(alpha, 1)
                    if T.max() < 0.15 or R.max() < 0.15 or I.max() < 0.1:
                        self.trainFlag = False
                        return
                    self.real_R = R.float().to(self.device)
                else:
                    I = input['I']
                    T = input['T']
            else:  # Test
                self.image_paths = input['B_paths']
                I = input['I']
                T = input['T']

        self.real_T = T.to(self.device)
        self.real_T_curv = self.load_curv(self.real_T)
        self.real_I = I.to(self.device)
        self.real_I_curv = self.load_curv(self.real_I)

    def get_c(self):
        b, c, w, h = self.real_I.shape
        return torch.zeros((b, self.opt.ngf * 4, w//4, h//4))

    def init(self):
        self.fake_T = torch.tensor(self.real_I)
        self.fake_Ts = [self.fake_T]
        self.fake_T_curv = torch.tensor(self.real_I_curv)
        self.fake_T_curvs = [self.fake_T_curv]

    def forward(self):
        self.init()
        i = 0
        fake_Ts, fake_curvs = self.netG_T(self.real_I, self.real_I_curv)
        self.fake_T = fake_Ts[-1]
        self.fake_Ts.extend(fake_Ts)
        self.fake_T_curv = fake_curvs[-1]
        self.fake_T_curvs.extend(fake_curvs)
        i += 1

        # clip operation in test
        if not self.isTrain:
            for i in range(len(self.fake_Ts)):
                self.fake_Ts[i] = torch.clamp(self.fake_Ts[i], min=0, max=1)
            for i in range(len(self.fake_T_curvs)):
                self.fake_T_curvs[i] = torch.clamp(self.fake_T_curvs[i], min=0, max=1)

    def backward_D_basic(self, netD, real, fake):
        """Calculate GAN loss for the discriminator

        Parameters:
            netD (network)      -- the discriminator D
            real (tensor array) -- real images
            fake (tensor array) -- images generated by a generator

        Return the discriminator loss.
        We also call loss_D.backward() to calculate the gradients.
        """
        # Real
        pred_real = netD(real)
        loss_D_real = self.criterionGAN(pred_real, True)
        # Fake
        pred_fake = netD(fake.detach())
        loss_D_fake = self.criterionGAN(pred_fake, False)
        # Combined loss and calculate gradients
        loss_D = (loss_D_real + loss_D_fake) * 0.5
        loss_D.backward()
        return loss_D

    def backward_D(self):
        """Calculate GAN loss for discriminator D_syn"""
        self.loss_D_syn = self.backward_D_basic(self.netD, self.real_T, self.fake_T)

    def backward_G(self):
        self.loss_idt_T = 0.0          # L_pixel on T
        self.loss_idt_R = 0.0          # L_pixel on R
        self.loss_res = 0.0            # L_residual: residual reconstruction loss
        self.loss_MP = 0.0             # L_MP: multi-scale perceptual loss
        self.loss_idt_T_curv = 0.0
        iter_num = len(self.fake_Ts)

        sigma = 1

        for i in range(iter_num):
            if i > 0:
                self.loss_idt_T += self.criterionIdt(self.fake_Ts[i], self.real_T) * np.power(sigma, iter_num - i)
                self.loss_MP += self.criterionVgg(self.fake_Ts[i], self.real_T)
                if i < iter_num-1:
                    self.loss_idt_T_curv += self.criterionGradient(self.fake_T_curvs[i], self.real_T_curv) * np.power(sigma, iter_num - i)

        self.loss_G = self.criterionGAN(self.netD(self.fake_T), True) * 0.01  # L_adv: adversarial loss
        self.loss_T = self.loss_idt_T + self.loss_MP + self.loss_G
        self.loss_T_curv = self.loss_idt_T_curv
        self.loss = self.loss_T + self.loss_T_curv

        self.loss.backward()

    def optimize_parameters(self):
        """Calculate losses, gradients, and update network weights; called in every training iteration"""
        # Pass invalid data
        if not self.trainFlag:
            self.trainFlag = True
            return

        self.optimizer_G.zero_grad()
        self.set_requires_grad([self.netD], False)  # Ds require no gradients when optimizing Gs
        self.forward()
        self.backward_G()
        self.optimizer_G.step()

        self.set_requires_grad([self.netD], True)
        self.optimizer_D.zero_grad()  # set D's gradients to zero
        self.backward_D()  # calculate gradients for D
        self.optimizer_D.step()

