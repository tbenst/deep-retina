# %load_ext autoreload
# %autoreload 1

import numpy as np
import collections
import pyret.filtertools as ft
import tensorflow as tf
load_model = tf.keras.models.load_model
from pathlib import Path
import h5py
import skvideo.io
import os
import functools

K = tf.keras.backend
from deepretina import config

import deepretina
import deepretina.experiments
import deepretina.models
import deepretina.core
import deepretina.metrics
import deepretina.utils

# %aimport deepretina
# %aimport deepretina.experiments
# %aimport deepretina.models
# %aimport deepretina.core
# %aimport deepretina.metrics
# %aimport deepretina.utils

D = deepretina
ExptSequence = D.experiments.ExptSequence
config.results_dir = "/home/tyler/scratch/results/"
config.results_dir = "/home/tyler/results/"
config.results_dir = "/storage/baccus/results/"
# config.results_dir = "/home/tyler/results/"
# config.data_dir = "/home/salamander/experiments/data/"
config.data_dir = "/storage/baccus/"

weights = Path(config.results_dir) / "G-CNN_josh_naturalmovie_2018.02.22-11.43.29" / "weights-066--5.115.h5"
weights = Path(config.results_dir) / "G-CNN_10_files_nogaussian_2018.02.19-22.24.53" / "weights-100--5.664.h5"
weights = Path(config.results_dir) / "G-CNN_17-11-10_17-12-09_naturalmovie_2018.03.12-11.16.03" / "weights-068--4.915.h5"
model = load_model(weights, custom_objects={"tf": tf, "ResizeMethod": D.models.ResizeMethod,
    "argmin_poisson": D.metrics.argmin_poisson,
    "matched_cc": D.metrics.matched_cc,
    "matched_mse": D.metrics.matched_mse,
    "matched_rmse": D.metrics.matched_rmse,
    })


datafile = Path(config.data_dir) / "17-12-09b-ssb" / "naturalmovie.h5"
datafile = Path(config.data_dir) / "17-12-16-ssb" / "naturalmovie.h5"
data = h5py.File(datafile, mode='r')

# %%

x = np.array(data["train"]["stimulus"])
y_train = x[41:]
x = D.experiments.rolling_window(x,40)
x = x[0:len(x)-1]
n = len(x)
x_train = model.predict(x, batch_size=1000)
x_train.shape
ntrain = int(np.floor(n*0.95))
nvalid = n - ntrain
train_data = ExptSequence([
    D.experiments.Exptdata(x_train[0:ntrain],y_train[0:ntrain])
    ])
valid_data = ExptSequence([
    D.experiments.Exptdata(x_train[ntrain:ntrain+nvalid],y_train[ntrain:ntrain+nvalid])
    ])
run_name = "Decoder_naturalmovie_17-11-10_17-12-09"
input_shape = train_data[0][0].shape[1:]
train_data[0][1].shape
steps_per_epoch = len(train_data)
steps_per_valid = len(valid_data)

# %%
@D.utils.context
def fit_decoder(train_data, input_shape, steps_per_epoch, run_name, valid_data, steps_per_valid):
    D.core.train_generator(D.models.decoder, train_data, input_shape, steps_per_epoch, run_name, valid_data, steps_per_valid, lr=1e-2, nb_epochs=250, bz=1000,the_metrics=[], loss='mse')

# %%
fit_decoder(train_data, input_shape, steps_per_epoch, run_name, valid_data, steps_per_valid)