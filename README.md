# Multi-stage Curvature-guided Network for Progressive Single Image Reflection Removal
(Updating)

An official implementation code for paper "Multi-stage Curvature-guided Network for Progressive Single Image Reflection Removal"

## Introduction

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
`python test.py --dataroot datasets --name MCDRNet --model MCDRN --dataset_mode mcdr --preprocess "" --no_flip --epoch final --gpu_ids 0`

## Acknowledgement

Our code is based on [IBCLN](https://github.com/JHL-HUST/IBCLN).

