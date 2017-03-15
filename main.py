from model_tf import LinearModel
from model_tf import RidgeLinearModel
from model_tf import BayesianLinearModel

from preprocess import Preprocessor

from util import load_dataset_csv
from plot import plot_3d

import numpy as np
import tensorflow as tf
import random
import os, sys, csv, argparse

from sklearn.model_selection import KFold

import logging

def load_data(x_path, y_path, shuffle=True):
    xs, ys = load_dataset_csv(x_path, y_path)
   
    n = len(xs)
    shuffle_indices = range(n)
    np.random.shuffle(shuffle_indices)

    return xs, ys, n

def filter_data(x):
    xs_normalize_filtered = x
    xs_normalize_filtered = xs_normalize_filtered[xs_normalize_filtered[:, 0] > 0.183774283]
    xs_normalize_filtered = xs_normalize_filtered[xs_normalize_filtered[:, 0] < 0.84]
    xs_normalize_filtered = xs_normalize_filtered[xs_normalize_filtered[:, 1] > 0.220027752]
    return xs_normalize_filtered

def crafted_gaussian_feature(means, sigmas):
    means = np.vstack((means, [0.13876, 0.508788159], [0.46253469, 0.092506938], [0.6475, 0.185]))
    sigmas = np.vstack((sigmas, [0.285, 0.5], [0.5, 0.285], [0.2, 0.1]))
    return means, sigmas

def get_model(args, shape):
    if args.model == 'ml':
        return LinearModel(shape, optimizer=args.optimizer, lr=args.lr)
    elif args.model == 'map':
        return RidgeLinearModel(shape, optimizer=args.optimizer, lr=args.lr, alpha=args.alpha)
    elif args.model == 'bayes':
        return BayesianLinearModel(shape, optimizer=args.optimizer, m0=args.m0, s0=args.s0, beta=args.beta)

def get_means_sigmas(args, x):
    if args.pre == 'kmeans':
        return Preprocessor().compute_gaussian_basis(x, deg=args.d, scale=args.scale)
    elif args.pre == 'grid':
        return Preprocessor().grid2d_means(0, 1.0, 0, 1.0, step=args.gsize, scale=args.scale)

def main(args):
    logging.basicConfig(format='[%(asctime)s] %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p', level=logging.INFO)
    logging.info('Loading data...')
    
    xs, ys, n = load_data(args.X, args.Y, shuffle=True)
    n_train = int(args.frac * n)
    
    rng = abs(args.max - args.min)
    
    preprocessor = Preprocessor()
    xs_n = preprocessor.normalize(xs, rng)
    xs_n_filtered = xs_n
    logging.info('Computing means and sigmas (%s)...' % args.pre)
    means, sigmas = get_means_sigmas(args, xs_n_filtered)

    def phi(x):
        pre = Preprocessor()
        return pre.gaussian(pre.normalize(x, rng), means, sigmas)
    
    logging.info('Preprocessing... (d = %d)' % means.shape[0])
    phi_xs = phi(xs)
    phi_xs_train, ys_train = phi_xs[:n_train], ys[:n_train]
    phi_xs_test, ys_test = phi_xs[n_train:], ys[n_train:]
 
    logging.info('Training... (optimizer = %s)' % args.optimizer)
    K = args.K
    kf = KFold(n_splits=args.K)

    w_best = None
    min_loss = 1e9
     
    LR = args.lr
    model = get_model(args, (len(phi_xs_train[0]),))
    logging.info('Using model %s (plot = %d)' % (args.model, args.plot))
    with tf.Session() as sess: 
        for train_index, validation_index in kf.split(phi_xs_train):
            sess.run(tf.global_variables_initializer())
            model.fit(sess, phi_xs_train[train_index], ys_train[train_index], epoch=args.epoch, batch_size=args.batch_size)
            loss = model.eval(sess, phi_xs_train[validation_index], ys_train[validation_index])
 
            logging.info('Validation loss = %f' % (loss))

            if loss < min_loss:
                w_best = model.get_weight(sess)
                min_loss = loss
            model.lr = LR

        model.set_weight(sess, w_best)
        loss = model.eval(sess, phi_xs_test, ys_test)
        logging.info('Test loss = %f' % (loss))

        def f(x):
            return np.round(np.clip(model.test(sess, x), args.min, args.max))

        if args.plot:
            logging.info('Plotting...')
            plot_3d(f, phi, args.min, args.max, args.min, args.max)
     

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--plot', help='enable plot', type=bool, default=False)
    parser.add_argument('--X', help='data', required=True, type=str)
    parser.add_argument('--Y', help='ground truth', required=True, type=str)
    parser.add_argument('--K', help='k-fold', type=int, default=3)
    parser.add_argument('--epoch', help='epoch', type=int, default=50)
    parser.add_argument('--batch_size', help='batch size', type=int, default=128)
    parser.add_argument('--lr', help='learning rate', type=float, default=0.5)
    parser.add_argument('--d', help='dimension of feature', type=int, default=512)
    parser.add_argument('--gsize', help='grid size', type=float, default=0.1)
    parser.add_argument('--scale', help='sigma scale', type=float, default=2.5)
    parser.add_argument('--min', help='minimum value of input space', type=float, default=0)
    parser.add_argument('--max', help='maximum value of input space', type=float, default=1081)
    parser.add_argument('--frac', help='fraction of training', type=float, default=0.8)
    parser.add_argument('--alpha', help='l2 penalty scale for map', type=float, default=0.01)
    parser.add_argument('--beta', help='beta (noise variance) for bayesian', type=float, default=1.0 / 0.2**2)
    parser.add_argument('--m0', help='m0 (mean) for bayesian', type=float, default=0.0)
    parser.add_argument('--s0', help='s0 (variance) for bayesian', type=float, default=2.0)
    parser.add_argument('--model', help='model',
            choices=['ml', 'map', 'bayes'], default='ml')
    parser.add_argument('--pre', help='preprocess approach',
            choices=['kmeans', 'grid'], default='grid')
    parser.add_argument('--optimizer', help='optimzier',
            choices=['ls', 'seq'], default='ls')



    args = parser.parse_args()

    main(args)