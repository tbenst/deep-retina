import numpy as np
import layers
from scipy.stats.stats import pearsonr
import matplotlib.pyplot as plt
from os.path import expanduser


class ClassifierTrainer(object):
  """ The trainer class performs SGD with momentum on a cost function """
  def __init__(self):
    self.step_cache = {} # for storing velocities in momentum update

  def train(self, X, y, X_val, y_val, 
            model, loss_function, 
            reg=0.0, dropout=1.0,
            learning_rate=1e-2, momentum=0, learning_rate_decay=0.95,
            update='momentum', sample_batches=True,
            num_epochs=30, batch_size=100, acc_frequency=None,
            augment_fn=None, predict_fn=None,
            verbose=False, save_plots=False):
    """
    Optimize the parameters of a model to minimize a loss function. We use
    training data X and y to compute the loss and gradients, and periodically
    check the accuracy on the validation set.

    Inputs:
    - X: Array of training data; each X[i] is a training sample.
    - y: Vector of training labels; y[i] gives the label for X[i].
    - X_val: Array of validation data
    - y_val: Vector of validation labels
    - model: Dictionary that maps parameter names to parameter values. Each
      parameter value is a numpy array.
    - loss_function: A function that can be called in the following ways:
      scores = loss_function(X, model, reg=reg)
      loss, grads = loss_function(X, model, y, reg=reg)
    - reg: Regularization strength. This will be passed to the loss function.
    - dropout: Amount of dropout to use. This will be passed to the loss function.
    - learning_rate: Initial learning rate to use.
    - momentum: Parameter to use for momentum updates.
    - learning_rate_decay: The learning rate is multiplied by this after each
      epoch.
    - update: The update rule to use. One of 'sgd', 'momentum', or 'rmsprop'.
    - sample_batches: If True, use a minibatch of data for each parameter update
      (stochastic gradient descent); if False, use the entire training set for
      each parameter update (gradient descent).
    - num_epochs: The number of epochs to take over the training data.
    - batch_size: The number of training samples to use at each iteration.
    - acc_frequency: If set to an integer, we compute the training and
      validation set accuracy after every acc_frequency iterations.
    - augment_fn: A function to perform data augmentation. If this is not
      None, then during training each minibatch will be passed through this
      before being passed as input to the network.
    - predict_fn: A function to mutate data at prediction time. If this is not
      None, then during each testing each minibatch will be passed through this
      before being passed as input to the network.
    - verbose: If True, print status after each epoch.

    Returns a tuple of:
    - best_model: The model that got the highest validation accuracy during
      training.
    - loss_history: List containing the value of the loss function at each
      iteration.
    - train_acc_history: List storing the training set accuracy at each epoch.
    - val_acc_history: List storing the validation set accuracy at each epoch.
    """

    N = X.shape[0]

    if sample_batches:
      iterations_per_epoch = N / batch_size # using SGD
    else:
      iterations_per_epoch = 1 # using GD
    num_iters = num_epochs * iterations_per_epoch
    epoch = 0
    best_val_acc = 0.0 # if you switch back to error, this needs to be np.inf
    best_model = {}
    loss_history = []
    train_acc_history = []
    val_acc_history = []
    weight_norm_history = []
    for it in xrange(num_iters):
      if verbose:
        if it % 10 == 0:  print 'starting iteration ', it

      # get batch of data
      if sample_batches:
        batch_mask = np.random.choice(N, batch_size)
        X_batch = X[batch_mask]
        y_batch = y[batch_mask]
      else:
        # no SGD used, full gradient descent
        X_batch = X
        y_batch = y

      # Maybe perform data augmentation
      if augment_fn is not None:
        X_batch = augment_fn(X_batch)

      # evaluate cost and gradient
      cost, grads = loss_function(X_batch, model, y_batch, reg=reg, dropout=dropout)
      loss_history.append(cost)

      # perform a parameter update
      for p in model:
        # compute the parameter step
        if update == 'sgd':
          dx = -learning_rate * grads[p]
        elif update == 'momentum':
          if not p in self.step_cache: 
            self.step_cache[p] = np.zeros(grads[p].shape)
          dx = np.zeros_like(grads[p]) # you can remove this after
          dx = momentum * self.step_cache[p] - learning_rate * grads[p]
          self.step_cache[p] = dx
        elif update == 'rmsprop':
          decay_rate = 0.99 # you could also make this an option
          if not p in self.step_cache: 
            self.step_cache[p] = np.zeros(grads[p].shape)
          dx = np.zeros_like(grads[p]) # you can remove this after
          self.step_cache[p] = self.step_cache[p] * decay_rate + (1.0 - decay_rate) * grads[p] ** 2
          dx = -(learning_rate * grads[p]) / np.sqrt(self.step_cache[p] + 1e-8)
        else:
          raise ValueError('Unrecognized update type "%s"' % update)

        # update the parameters
        model[p] += dx

      # every epoch perform an evaluation on the validation set
      first_it = (it == 0)
      epoch_end = (it + 1) % iterations_per_epoch == 0
      acc_check = (acc_frequency is not None and it % acc_frequency == 0)
      if first_it or epoch_end or acc_check:
        if it > 0 and epoch_end:
          # decay the learning rate
          learning_rate *= learning_rate_decay
          epoch += 1

        # evaluate train accuracy
        if N > 1000:
          train_mask = np.random.choice(N, 1000)
          X_train_subset = X[train_mask]
          y_train_subset = y[train_mask]
        else:
          X_train_subset = X
          y_train_subset = y
        # Computing a forward pass with a batch size of 1000 will is no good,
        # so we batch it
        if sample_batches:
            iterations = X_train_subset.shape[0] / batch_size

            scores       = np.zeros(y_train_subset.shape)
            y_pred_train = np.zeros(y_train_subset.shape)
            for it in xrange(iterations):
                batch_mask = np.random.choice(X_train_subset.shape[0], batch_size)
                X_batch    = X_train_subset[batch_mask]
                y_batch    = y_train_subset[batch_mask]
                y_pred_train[it*batch_size:(it+1)*batch_size] = loss_function(X_batch, model).squeeze()
        else:
            y_pred_train = loss_function(X_train_subset, model) # calling loss_function with y=None returns rates
        

        train_acc, _ = pearsonr(y_pred_train, y_train_subset) 
        train_acc_history.append(train_acc)

        # evaluate val accuracy, but split the validation set into batches
        if sample_batches:
            iterations = X_val.shape[0] / batch_size

            scores     = np.zeros(y_val.shape)
            y_pred_val = np.zeros(y_val.shape)
            for it in xrange(iterations):
                batch_mask  = np.random.choice(X_val.shape[0], batch_size)
                X_val_batch = X_val[batch_mask]
                y_val_batch = y_val[batch_mask]
                y_pred_val[it*batch_size:(it+1)*batch_size] = loss_function(X_val_batch, model).squeeze()
        else:
            y_pred_val = loss_function(X_val, model) # calling loss_function with y=None returns rates


        val_acc, _ = pearsonr(y_pred_val, y_val)
        val_acc_history.append(val_acc)
        
        # keep track of the best model based on validation accuracy
        if val_acc > best_val_acc:
          # make a copy of the model
          best_val_acc = val_acc
          best_model = {}
          for p in model:
            best_model[p] = model[p].copy()

        # keep track of weight norms
        weight_norm_history.append(np.sum([np.sum(model[W]*model[W]) for W in ['W1', 'W2']]))

        # print progress if needed
        if verbose:
          print ('Finished epoch %d / %d: cost %f, train: %f, val %f, lr %e'
                 % (epoch, num_epochs, cost, train_acc, val_acc, learning_rate))

        if save_plots:
          import matplotlib.pyplot as plt

          plt.subplot(3, 1, 1)
          plt.plot(loss_history)
          plt.title('Loss history', fontsize=16)
          plt.xlabel('Iteration', fontsize=16)
          plt.ylabel('Loss', fontsize=16)

          plt.subplot(3, 1, 2)
          plt.plot(train_acc_history)
          plt.plot(val_acc_history)
          plt.legend(['Training corr coeff', 'Validation corr coeff'], loc='lower right')
          plt.xlabel('Acc Frequency', fontsize=16)
          plt.ylabel('Correlation coefficient', fontsize=16)

          plt.subplot(3, 1, 3)
          plt.plot(weight_norm_history)
          plt.title('Weight norm', fontsize=16)
          plt.xlabel('Acc Frequency', fontsize=16)
          plt.ylabel('L2 Norm of W1 and W2', fontsize=16)

          fig_dir  = '~/Git/deepRGC/optimization_snapshots'
          filename = 'Epoch%sIteration%i.png' %(epoch, it)
          savefig(fig_dir + filename)


    if verbose:
      print 'finished optimization. best validation accuracy: %f' % (best_val_acc, )
    # return the best model and the training history statistics
    return best_model, loss_history, train_acc_history, val_acc_history


  def train_memmap(self, X, y, train_inds, val_inds, model, loss_function, 
                   reg=0.0, dropout=1.0, learning_rate=1e-2, momentum=0, 
                   learning_rate_decay=0.95, update='momentum', 
                   sample_batches=True, num_epochs=30, batch_size=100, 
                   acc_frequency=None, augment_fn=None, predict_fn=None,
                   verbose=False, save_plots=False, machine='LaneMacbook'):
    """
    Optimize the parameters of a model to minimize a loss function. We use
    training data X and y to compute the loss and gradients, and periodically
    check the accuracy on the validation set.

    Inputs:
    - X: Array of all data; each X[i] is a training sample.
    - y: Vector of all labels; y[i] gives the label for X[i].
    - train_inds: vector mask for training data
    - test_inds: vector mask for test data
    - model: Dictionary that maps parameter names to parameter values. Each
      parameter value is a numpy array.
    - loss_function: A function that can be called in the following ways:
      scores = loss_function(X, model, reg=reg)
      loss, grads = loss_function(X, model, y, reg=reg)
    - reg: Regularization strength. This will be passed to the loss function.
    - dropout: Amount of dropout to use. This will be passed to the loss function.
    - learning_rate: Initial learning rate to use.
    - momentum: Parameter to use for momentum updates.
    - learning_rate_decay: The learning rate is multiplied by this after each
      epoch.
    - update: The update rule to use. One of 'sgd', 'momentum', or 'rmsprop'.
    - sample_batches: If True, use a minibatch of data for each parameter update
      (stochastic gradient descent); if False, use the entire training set for
      each parameter update (gradient descent).
    - num_epochs: The number of epochs to take over the training data.
    - batch_size: The number of training samples to use at each iteration.
    - acc_frequency: If set to an integer, we compute the training and
      validation set accuracy after every acc_frequency iterations.
    - augment_fn: A function to perform data augmentation. If this is not
      None, then during training each minibatch will be passed through this
      before being passed as input to the network.
    - predict_fn: A function to mutate data at prediction time. If this is not
      None, then during each testing each minibatch will be passed through this
      before being passed as input to the network.
    - verbose: If True, print status after each epoch.

    Returns a tuple of:
    - best_model: The model that got the highest validation accuracy during
      training.
    - loss_history: List containing the value of the loss function at each
      iteration.
    - train_acc_history: List storing the training set accuracy at each epoch.
    - val_acc_history: List storing the validation set accuracy at each epoch.
    """

    N = y[train_inds].shape[0] #X.shape[0]

    if sample_batches:
      iterations_per_epoch = N / batch_size # using SGD
    else:
      iterations_per_epoch = 1 # using GD
    num_iters = num_epochs * iterations_per_epoch
    epoch = 0
    best_val_acc = 0.0 # if you switch back to error, this needs to be np.inf
    best_model = {}
    loss_history = []
    train_acc_history = []
    val_acc_history = []
    weight_norm_history = []
    max_weight_history = []
    min_weight_history = []
    max_dw_history = []
    min_dw_history = []
    mean_weight_history = []
    mean_dw_history = []
    train_mse_history = []
    val_mse_history = []
    train_max_rates_history = []
    train_min_rates_history = []
    train_mean_rates_history = []
    val_max_rates_history = []
    val_min_rates_history = []
    val_mean_rates_history = []
    max_true_history = []
    min_true_history = []
    mean_true_history = []

    if machine == 'LaneMacbook':
      fig_dir = '/Users/lmcintosh/Git/deepRGC/optimization_snapshots/'
    elif machine == 'Eggplant':
      fig_dir = expanduser('~/deep-retina/optimization-screenshots/')

    for it in xrange(num_iters):
      if verbose:
        if it % 10 == 0:  print 'starting iteration ', it

      # get batch of data
      if sample_batches:
        batch_mask = train_inds[np.random.choice(N, batch_size, replace=False)]
      else:
        # no SGD used, full gradient descent
        batch_mask = train_inds

      # Maybe perform data augmentation
      if augment_fn is not None:
        X_batch = augment_fn(X[batch_mask])

      # evaluate cost and gradient
      cost, grads = loss_function(X[batch_mask], model, y[batch_mask], reg=reg, dropout=dropout)
      loss_history.append(cost)

      # perform a parameter update
      for p in model:
        # compute the parameter step
        if update == 'sgd':
          dx = -learning_rate * grads[p]
        elif update == 'momentum':
          if not p in self.step_cache: 
            self.step_cache[p] = np.zeros(grads[p].shape)
          dx = momentum * self.step_cache[p] - learning_rate * grads[p]
          self.step_cache[p] = dx
        elif update == 'rmsprop':
          decay_rate = 0.99 # you could also make this an option
          if not p in self.step_cache: 
            self.step_cache[p] = np.zeros(grads[p].shape)
          self.step_cache[p] = self.step_cache[p] * decay_rate + (1.0 - decay_rate) * grads[p] ** 2
          dx = -(learning_rate * grads[p]) / np.sqrt(self.step_cache[p] + 1e-8)
        else:
          raise ValueError('Unrecognized update type "%s"' % update)

        # update the parameters
        model[p] += dx

        if p == 'W1':
            max_dw_history.append(np.max(dx))
            min_dw_history.append(np.min(dx))
            mean_dw_history.append(np.mean(dx))

            max_weight_history.append(np.max(model[p]))
            min_weight_history.append(np.min(model[p]))
            mean_weight_history.append(np.mean(model[p]))

      # every epoch perform an evaluation on the validation set
      first_it = (it == 0)
      epoch_end = (it + 1) % iterations_per_epoch == 0
      acc_check = (acc_frequency is not None and it % acc_frequency == 0)
      if first_it or epoch_end or acc_check:
        if it > 0 and epoch_end:
          # decay the learning rate
          learning_rate *= learning_rate_decay
          epoch += 1

        # evaluate train accuracy
        if N > 1000:
          train_mask = train_inds[np.random.choice(N, 1000, replace=False)]
        else:
          train_mask = train_inds

        # Computing a forward pass with a batch size of 1000 will is no good,
        # so we batch it
        if sample_batches:
            M = y[train_mask].shape[0]
            assert M % batch_size == 0, 'Size of training data must be divisible by %d.' %(batch_size)
            iterations = M / batch_size

            y_pred_train = np.zeros(y[train_mask].shape)
            for b in xrange(iterations):
                batch_mask = train_mask[b*batch_size:(b+1)*batch_size]
                y_pred_train[b*batch_size:(b+1)*batch_size] = loss_function(X[batch_mask], model).squeeze()
        else:
            y_pred_train = loss_function(X[train_mask], model) # calling loss_function with y=None returns rates
        
        train_acc, _ = pearsonr(y_pred_train, y[train_mask]) 
        train_acc_history.append(train_acc)
        train_mse_history.append(np.mean((y_pred_train - y[train_mask])**2))
        train_max_rates_history.append(np.max(y_pred_train))
        train_min_rates_history.append(np.min(y_pred_train))
        train_mean_rates_history.append(np.mean(y_pred_train))
        max_true_history.append(np.max(y[train_mask]))
        min_true_history.append(np.min(y[train_mask]))
        mean_true_history.append(np.mean(y[train_mask]))

        if not first_it:
            print 'Train preds in (%f, %f), val preds in (%f, %f), truth in (%f, %f).' %(train_min_rates_history[-1],
                                                                                    train_max_rates_history[-1],
                                                                                    val_min_rates_history[-1],
                                                                                    val_max_rates_history[-1],
                                                                                    min_true_history[-1],
                                                                                    max_true_history[-1])


        # evaluate val accuracy, but split the validation set into batches
        if sample_batches:
            M = y[val_inds].shape[0]
            assert M % batch_size == 0, 'Size of val data must be divisible by %d.' %(batch_size)
            iterations = M / batch_size

            y_pred_val = np.zeros(y[val_inds].shape)
            for b in xrange(iterations):
                batch_mask  = val_inds[b*batch_size:(b+1)*batch_size]
                y_pred_val[b*batch_size:(b+1)*batch_size] = loss_function(X[batch_mask], model).squeeze()
        else:
            y_pred_val = loss_function(X[val_inds], model) # calling loss_function with y=None returns rates


        val_acc, _ = pearsonr(y_pred_val, y[val_inds])
        val_acc_history.append(val_acc)
        val_mse_history.append(np.mean((y_pred_val - y[val_inds])**2))
        val_max_rates_history.append(np.max(y_pred_val))
        val_min_rates_history.append(np.min(y_pred_val))
        val_mean_rates_history.append(np.mean(y_pred_val))
        
        # keep track of the best model based on validation accuracy
        if val_acc > best_val_acc:
          # make a copy of the model
          best_val_acc = val_acc
          best_model = {}
          for p in model:
            best_model[p] = model[p].copy()


        # keep track of weight norms
        weight_norm_history.append(np.sum([np.sum(model[W]*model[W]) for W in ['W1', 'W2']]))


        # print progress if needed
        if verbose:
          print ('Finished epoch %d / %d: cost %f, train: %f, val %f, lr %e'
                 % (epoch, num_epochs, cost, train_acc, val_acc, learning_rate))

        if save_plots and not epoch_end:
          fig = plt.gcf()
          fig.set_size_inches((20,24))
          ax = plt.subplot(4, 2, 1)
          ax.plot(loss_history, 'k')
          ax.set_title('Loss history', fontsize=16)
          #ax.set_xlabel('Iteration', fontsize=16)
          ax.set_ylabel('Loss', fontsize=14)

          ax = plt.subplot(4, 2, 2)
          ax.plot(train_acc_history, 'b')
          ax.plot(val_acc_history, 'g')
          ax.set_title('Correlation Coefficients', fontsize=16)
          ax.legend(['Training corr coeff', 'Validation corr coeff'], loc='lower right')
          #ax.set_xlabel('Acc Frequency', fontsize=16)
          ax.set_ylabel('Correlation coefficient', fontsize=14)

          ax = plt.subplot(4, 2, 3)
          ax.plot(train_mse_history, 'b')
          ax.plot(val_mse_history, 'g')
          ax.set_title('Mean squared error', fontsize=16)
          ax.legend(['Training mse', 'Validation mse'], loc='lower right')
          ax.set_ylabel('Mean squared error', fontsize=14)

          ax = plt.subplot(4, 2, 4)
          ax.plot(weight_norm_history, 'k')
          ax.set_title('Weight norm', fontsize=16)
          #ax.set_xlabel('Acc Frequency', fontsize=16)
          ax.set_ylabel('L2 Norm of W1 and W2', fontsize=14)

          ax = plt.subplot(4, 2, 5)
          ax.plot(max_weight_history, 'b')
          ax.plot(min_weight_history, 'b')
          ax.plot(mean_weight_history, 'r')
          ax.set_title('Value stats for W1', fontsize=16)
          ax.set_ylabel('W1 stats', fontsize=14)

          ax = plt.subplot(4, 2, 6)
          ax.plot(max_dw_history, 'g')
          ax.plot(min_dw_history, 'g')
          ax.plot(mean_dw_history, 'r')
          ax.set_title('Gradient stats for W1', fontsize=16)
          ax.set_ylabel('dW1 stats', fontsize=14)

          ax = plt.subplot(4, 2, 7)
          ax.plot(train_max_rates_history, 'b')
          ax.plot(train_min_rates_history, 'b')
          ax.plot(val_max_rates_history, 'g')
          ax.plot(val_min_rates_history, 'g')
          ax.plot(train_mean_rates_history, 'b', alpha=0.7, linewidth=2)
          ax.plot(val_mean_rates_history, 'g', alpha=0.7, linewidth=2)
          ax.plot(max_true_history, 'k', alpha=0.7)
          ax.plot(min_true_history, 'k', alpha=0.7)
          ax.plot(mean_true_history, 'k', alpha=0.4, linewidth=2)
          ax.set_title('Rates stats for train, val, and true', fontsize=16)
          ax.set_ylabel('prediction stats', fontsize=14)

          ax = plt.subplot(4, 2, 8)
          ax.plot(y_pred_train[:250], 'r')
          ax.plot(y[train_mask][:250], 'k')
          ax.set_title('Real (black) vs predicted (red) response', fontsize=16)
          ax.set_ylabel('Output', fontsize=14)

          plt.tight_layout()

          filename = 'Epoch%sIteration%i.png' %(epoch, it)
          plt.savefig(fig_dir + filename, bbox_inches='tight')

          plt.close()

    if verbose:
      print 'finished optimization. best validation accuracy: %f' % (best_val_acc, )
    # return the best model and the training history statistics
    return best_model, loss_history, train_acc_history, val_acc_history