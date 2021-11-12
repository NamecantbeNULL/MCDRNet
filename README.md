# Multi-stage Curvature-guided Network for Progressive Single Image Reflection Removal
(Updating)

An official implementation code for paper "Multi-stage Curvature-guided Network for Progressive Single Image Reflection Removal"

## Introduction

Thanks to the powerful learning capability, deep neural networks (DNNs) have acquired broad applications in single image reflection removal. The DNN-based algorithms relax the constraints of specific priors and learn to generate visually pleasant background layers from massive training data. However, most of them employ a single-stage network, directly mapping the original input to the ultimate result, which may lead to obvious reflection residue or even failure. To mitigate this deficiency, in this work, we propose a Multi-stage Curvatureguided De-Reflection Network (MCDRNet), which combines multiple network architectures in a unified framework to progressively remove the reflection. Our framework consists of three stages, where the encoder-decoders are exploited in the first two stages to recover the semantic components and a variant ResNet is leveraged in the last stage to generate the details in the background layer. In the first two stages, to introduce the structural guidance for the reflection removal, we cascade another decoder branch to restore the curvature map of the background. In addition, at the end of the first two stages, instead of directly passing the intermediate estimates to the next stage, we propose a Non-local Attention Module (NAM) to augment and transmit the features from decoders. Extensive experimental results on several public datasets demonstrate that the proposed MCDRNet outperforms the state-of-the-art methods quantitatively and generates visually better reflection removal results. 

## Requisites

* Pytorch 1.6.0
* Python 3
* Linux

## Test

### Prepare Test Data

Download and unzip the [test set](https://drive.google.com/file/d/1bDYvzkdYBKw8UbOxTje7Sya1Rl_Nl8Oz/view?usp=sharing), and then copy them to `datasets`.

### Download Pre-trained Model

Download and unzip our [pre-trained model](https://drive.google.com/file/d/1lJnpe2vbvM7sASKgYE0W-T5d8L9vVvW8/view?usp=sharing), and then copy them to `checkpoints/MCDRNet`.

### Run

You can run `bash test.sh`
or equivalently:
```python
python test.py --dataroot datasets --name MCDRNet --model MCDRN --dataset_mode mcdr --preprocess "" --no_flip --epoch final --gpu_ids 0
```

## Acknowledgement

Our code is based on [IBCLN](https://github.com/JHL-HUST/IBCLN).

