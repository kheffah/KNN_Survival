#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Aug 27 01:56:26 2017

@author: mohamed

Survival NCA (Neighborhood Component Analysis)
"""

# Append relevant paths
import os
import sys

def conditionalAppend(Dir):
    """ Append dir to sys path"""
    if Dir not in sys.path:
        sys.path.append(Dir)

cwd = os.getcwd()
conditionalAppend(cwd)

import _pickle
import numpy as np
import tensorflow as tf
#from scipy.io import loadmat, savemat
#from matplotlib import cm
import matplotlib.pylab as plt

#import logging
import datetime

import ProjectUtils as pUtils
import SurvivalUtils as sUtils
import DataManagement as dm

#import NCA_graph as cgraph
import NCA_graph as cgraph
import KNNSurvival as knn

#raise(Exception)

#%%============================================================================
# NCAmodel class (trainable model)
#==============================================================================

class SurvivalNCA(object):
    
    """
    Extension of NCA to right-censored settings.
    
    Key references: 
        
        1- J Goldberger, GE Hinton, ST Roweis, RR Salakhutdinov. 
        Neighbourhood components analysis. 
        Advances in neural information processing systems, 513-520
        
        2- Yang, W., K. Wang, W. Zuo. 
        Neighborhood Component Feature Selection for High-Dimensional Data.
        Journal of Computers. Vol. 7, Number 1, January, 2012.
        
    """
    
    # Set class attributes
    ###########################################################################
    
    # default graph params
    default_graphParams = {'OPTIM': 'GD',
                           'LEARN_RATE': 0.01,
                           'per_split_feats': 500,
                           'ROTATE': False,
                           }
    userspecified_graphParams = ['dim_input',]
    
    # default graph hyperparams
    default_graph_hyperparams = {'LAMBDA': 0,
                                'ALPHA': 0.5,
                                'SIGMA': 1.0,
                                'DROPOUT_FRACTION': 0.1,
                                }
    userspecified_graph_hyperparams = []
    
    
    # Init
    ###########################################################################
    
    def __init__(self, 
                 RESULTPATH, description="", 
                 LOADPATH = None):
        
        """Instantiate a survival NCA object"""
        
        if LOADPATH is not None:
            
            # Load existing model
            self.load(LOADPATH)
            
            # overwrite loaded paths
            self.RESULTPATH = RESULTPATH
            
        else:
            
            # Set instance attributes
            #==================================================================
            
            self.RESULTPATH = RESULTPATH
            self.LOGPATH = self.RESULTPATH + "model/logs/"
            self.WEIGHTPATH = self.RESULTPATH + "model/weights/"
            
            # prefix to all saved results
            self.description = description
            
            # new model inital attributes
            self.Costs_epochLevel_train = []
            self.CIs_train = []
            self.CIs_valid = []
            self.BATCHES_RUN = 0
            self.EPOCHS_RUN = 0
            
            # Create output dirs
            #==================================================================
            
            self._makeSubdirs()
            
            # Configure logger - will not work with iPython
            #==================================================================
            
            #timestamp = str(datetime.datetime.today()).replace(' ','_')
            #logging.basicConfig(filename = self.LOGPATH + timestamp + "_RunLogs.log", 
            #                    level = logging.INFO,
            #                    format = '%(levelname)s:%(message)s')
                                
            
    #%%===========================================================================
    # Miscellaneous methods
    #==============================================================================
    
    # The following load/save methods are inspired by:
    # https://stackoverflow.com/questions/2345151/
    # how-to-save-read-class-wholly-in-python
        
    def save(self):
        
        """save relevant attributes as ModelAttributes.pkl"""
        
        #pUtils.Log_and_print("Saving relevant attributes ...")

        attribs = self.getModelInfo()
                
        with open(self.RESULTPATH + 'model/' + self.description + \
                  'ModelAttributes.pkl','wb') as f:
            _pickle.dump(attribs, f)
    
    #==========================================================================
    
    def load(self, LOADPATH):
        
        """load ModelAttributes.pkl"""
        
        print("Loading model attributes ...")
        
        with open(LOADPATH,'rb') as f:
            attribs = _pickle.load(f)
            
        # unpack dict
        self.RESULTPATH = attribs['RESULTPATH']
        self.description = attribs['description']
        self.Costs_epochLevel_train = attribs['Costs_epochLevel_train']
        self.CIs_train = attribs['CIs_train']
        self.CIs_valid = attribs['CIs_valid']        
        self.BATCHES_RUN = attribs['BATCHES_RUN']
        self.EPOCHS_RUN = attribs['EPOCHS_RUN']
        self.COMPUT_GRAPH_PARAMS = attribs['COMPUT_GRAPH_PARAMS']
        self.LOGPATH = attribs['LOGPATH']
        self.WEIGHTPATH = attribs['WEIGHTPATH']
            
    #==========================================================================
    
    def getModelInfo(self):
        
        """ Returns relevant model attributes"""
        
        attribs = {
            'RESULTPATH' : self.RESULTPATH,
            'description' : self.description,
            'Costs_epochLevel_train': self.Costs_epochLevel_train,
            'CIs_train': self.CIs_train,
            'CIs_valid': self.CIs_valid,
            'BATCHES_RUN': self.BATCHES_RUN,
            'EPOCHS_RUN': self.EPOCHS_RUN,
            'COMPUT_GRAPH_PARAMS': self.COMPUT_GRAPH_PARAMS,
            'LOGPATH': self.LOGPATH,
            'WEIGHTPATH': self.WEIGHTPATH,
            }
        
        return attribs
    
    #==========================================================================
    
    def reset_TrainHistory(self):
        
        """Resets training history (Costs etc)"""  
        
        self.EPOCHS_RUN = 0
        self.BATCHES_RUN = 0    
        self.Costs_epochLevel_train = []
        self.CIs_train = []
        self.CIs_valid = []
        #self.save()
        
    #==========================================================================    
    
    def _makeSubdirs(self):
        
        """ Create output directories"""
        
        # Create relevant result subdirectories
        pUtils.makeSubdir(self.RESULTPATH, 'plots')
        pUtils.makeSubdir(self.RESULTPATH, 'ranks')
        
        # Create a subdir to save the model
        pUtils.makeSubdir(self.RESULTPATH, 'model')
        pUtils.makeSubdir(self.RESULTPATH + 'model/', 'weights')
        pUtils.makeSubdir(self.RESULTPATH + 'model/', 'logs')
        
    #==========================================================================    
    
    def _update_timestamp(self):
        
        """ Update time stamp """
        
        timestamp = str(datetime.datetime.today()).replace(' ','_')
        self.timestamp = timestamp.replace(":", '_')
        
    
    #%%============================================================================
    # build computational graph
    #==============================================================================
    
    def build_computational_graph(self, COMPUT_GRAPH_PARAMS={}):
        
        """ 
        Build the computational graph for this model
        At least, no of dimensions ('D') must be provided
        """
        
        print("\nBuilding computational graph.")
        
        # Now that the computationl graph is provided D is always fixed
        self.D = COMPUT_GRAPH_PARAMS['dim_input']

        # Params for the computational graph
        self.COMPUT_GRAPH_PARAMS = \
            pUtils.Merge_dict_with_default(\
                    dict_given = COMPUT_GRAPH_PARAMS,
                    dict_default = self.default_graphParams,
                    keys_Needed = self.userspecified_graphParams)
                    
        # instantiate computational graph
        self.graph = cgraph.comput_graph(**self.COMPUT_GRAPH_PARAMS)
        
        print("Finished building graph.")
    
    
    #%%============================================================================
    #  Run session   
    #==============================================================================
        
    def train(self, 
            features, survival, censored,
            features_valid = None, 
            survival_valid = None, 
            censored_valid = None,
            graph_hyperparams={},
            BATCH_SIZE = 20,
            PLOT_STEP = 10,
            MODEL_SAVE_STEP = 10,
            MAX_ITIR = 100,
            MODEL_BUFFER = 4,
            EARLY_STOPPING = False,
            MONITOR=True,
            PLOT=True,
            K=35,
            Method='cumulative-time',
            norm=2):
                
        """
        train a survivalNCA model
        features - (N,D) np array
        survival and censored - (N,) np array
        """
        
        #pUtils.Log_and_print("Training survival NCA model.")
        
        
        # Initial preprocessing and sanity checks
        #====================================================================== 
        
        #pUtils.Log_and_print("Initial preprocessing.")
        
        D = features.shape[1]

        assert len(features.shape) == 2
        assert len(survival.shape) == 1
        assert len(censored.shape) == 1
        
        USE_VALID = False
        if features_valid is not None:
            USE_VALID = True
            assert (features_valid.shape[1] == D)
            assert (survival_valid is not None)
            assert (censored_valid is not None)
            
        if EARLY_STOPPING:
            assert USE_VALID
        
        # Define computational graph
        #======================================================================        
        
        graph_hyperparams = \
            pUtils.Merge_dict_with_default(\
                    dict_given = graph_hyperparams,
                    dict_default = self.default_graph_hyperparams,
                    keys_Needed = self.userspecified_graph_hyperparams)
        
        
        # Begin session
        #======================================================================  
        
        #print("Running TF session.")
        #pUtils.Log_and_print("Running TF session.")

        with tf.Session() as sess:
            
            
            # Initial ground work
            #==================================================================
            
            # op to save/restore all the variables
            saver = tf.train.Saver()
            
            if "checkpoint" in os.listdir(self.WEIGHTPATH):
                # load existing weights 
                #pUtils.Log_and_print("Restoring saved model ...")                
                saver.restore(sess, self.WEIGHTPATH + self.description + ".ckpt")
                #pUtils.Log_and_print("Model restored.")                
                
            else:                
                # start a new model
                sess.run(tf.global_variables_initializer())
                
            # for tensorboard visualization
            #train_writer = tf.summary.FileWriter(self.RESULTPATH + 'model/tensorboard', 
            #                                     sess.self.graph)

            # Define some methods
            #==================================================================


            # periodically save model
            def _saveTFmodel():

                """Saves model weights using tensorflow saver"""
            
                # save weights                        
                #pUtils.Log_and_print("\nSaving TF model weights...")
                #save_path = saver.save(sess, \
                #                self.WEIGHTPATH + self.description + ".ckpt")
                #pUtils.Log_and_print("Model saved in file: %s" % save_path)
            
                # save attributes
                self.save()
             
            
            # monitor
            def _monitorProgress(snapshot_idx=None):

                """
                Monitor cost - save txt and plots cost
                """
                # find min epochs to display in case of keyboard interrupt
                max_epoch = np.min([len(self.Costs_epochLevel_train),
                                    len(self.CIs_train),
                                    len(self.CIs_valid)])
                
                # concatenate costs
                costs = np.array(self.Costs_epochLevel_train[0:max_epoch])
                cis_train = np.array(self.CIs_train[0:max_epoch])
                if USE_VALID:
                    cis_valid = np.array(self.CIs_valid[0:max_epoch])
                else:
                    cis_valid = None
                
                epoch_no = np.arange(max_epoch)
                costs = np.concatenate((epoch_no[:, None], costs[:, None]), axis=1)
                cis_train = np.concatenate((epoch_no[:, None], cis_train[:, None]), axis=1)
                
                # Saving raw numbers for later reference
                savename= self.RESULTPATH + "plots/" + self.description + self.timestamp
                
                with open(savename + '_costs.txt', 'wb') as f:
                    np.savetxt(f, costs, fmt='%s', delimiter='\t')

                with open(savename + '_cis_train.txt', 'wb') as f:
                    np.savetxt(f, cis_train, fmt='%s', delimiter='\t')

                if USE_VALID:
                    with open(savename + '_cis_valid.txt', 'wb') as f:
                        np.savetxt(f, cis_valid, fmt='%s', delimiter='\t')
                
                #
                # Note, plotting would not work when running
                # this using screen (Xdisplay is not supported)
                #
                if PLOT:
                    self._plotMonitor(arr= costs,
                                      title= "Cost vs. epoch", 
                                      xlab= "epoch", ylab= "Cost", 
                                      savename= savename + "_costs.svg")
                    self._plotMonitor(arr= cis_train, arr2= cis_valid,
                                      title= "C-index vs. epoch", 
                                      xlab= "epoch", ylab= "C-index", 
                                      savename= savename + "_Ci.svg",
                                      snapshot_idx=snapshot_idx)
    
            # Begin epochs
            #==================================================================
            
            try: 
                itir = 0
                
                if MONITOR:
                    print("\n\tepoch\tcost\tCi_train\tCi_valid")
                    print("\t----------------------------------------------")
                
                knnmodel = knn.SurvivalKNN(self.RESULTPATH, description=self.description)
                
                # Initialize weights buffer 
                # (keep a snapshot of model for early stopping)
                # each "channel" in 3rd dim is one snapshot of the model
                if USE_VALID:
                    Ws = np.zeros((D, D, MODEL_BUFFER))
                    Cis = []
                
                while itir < MAX_ITIR:
                    
                    #pUtils.Log_and_print("\n\tTraining epoch {}\n".format(self.EPOCHS_RUN))
                    
                    itir += 1
                    cost_tot = 0
                    self._update_timestamp()
            
                    # Divide into balanced batches
                    #==========================================================
                    
                    n = censored.shape[0]
                    
                    # Get balanced batches (if relevant)
                    if BATCH_SIZE < n:
                        # Shuffle so that training batches differ every epoch
                        idxs = np.arange(features.shape[0]);
                        np.random.shuffle(idxs)
                        features = features[idxs, :]
                        survival = survival[idxs]
                        censored  = censored[idxs]
                        # stochastic mini-batch GD
                        batchIdxs = dm.get_balanced_batches(censored, 
                                                            BATCH_SIZE=BATCH_SIZE)
                    else:
                        # Global GD
                        batchIdxs = [np.arange(n)]
                                      
                    # Run over training set
                    #==========================================================
                            
                    for batchidx, batch in enumerate(batchIdxs):
                        
                        # Getting at-risk groups
                        t_batch, o_batch, at_risk_batch, x_batch = \
                            sUtils.calc_at_risk(survival[batch], 
                                                1-censored[batch],
                                                features[batch, :])
                                                
                        # Get at-risk mask (to be multiplied by Pij)
                        n_batch = t_batch.shape[0]
                        
                        # print("\tbatch {} of {}".format(batchidx, n_batch-1))                        
                        
                        Pij_mask = np.zeros((n_batch, n_batch))
                        for idx in range(n_batch):
                            # only observed cases
                            if o_batch[idx] == 1:
                                # only at-risk cases
                                Pij_mask[idx, at_risk_batch[idx]:] = 1
                        
                        # run optimizer and fetch cost
                        feed_dict = {self.graph.X_input: x_batch,
                                     self.graph.Pij_mask: Pij_mask,
                                     self.graph.ALPHA: graph_hyperparams['ALPHA'],
                                     self.graph.LAMBDA: graph_hyperparams['LAMBDA'],
                                     self.graph.SIGMA: graph_hyperparams['SIGMA'],
                                     self.graph.DROPOUT_FRACTION: graph_hyperparams['DROPOUT_FRACTION'],
                                     }  
                        _, cost = sess.run([self.graph.optimizer, self.graph.cost], feed_dict = feed_dict)
                                                 
                        # normalize cost for sample size
                        cost = cost / len(batch)
                        
                        # record/append cost
                        #self.Costs_batchLevel_train.append(cost)                  
                        cost_tot += cost                        

                        #pUtils.Log_and_print("\t\tTraining: Batch {} of {}, cost = {}".\
                        #     format(batchidx, len(batchIdxs)-1, round(cost[0], 3)))

                    # Now get final NCA matrix (without dropput)
                    #==========================================================

                    feed_dict[self.graph.DROPOUT_FRACTION] = 0
                    W_grabbed = self.graph.W.eval(feed_dict = feed_dict)
                    
                    # Get Ci for training/validation set
                    #==========================================================
            
                    # transform
                    x_train_transformed = np.dot(features, W_grabbed)
                    if USE_VALID:
                        x_valid_transformed = np.dot(features_valid, W_grabbed)
            
                    # get neighbor indices    
                    neighbor_idxs_train = \
                        knnmodel._get_neighbor_idxs(x_train_transformed, 
                                                    x_train_transformed, 
                                                    norm=norm)
                    if USE_VALID:
                        neighbor_idxs_valid = \
                            knnmodel._get_neighbor_idxs(x_valid_transformed, 
                                                        x_train_transformed, 
                                                        norm=norm)
                    
                    # Predict training/validation set
                    _, Ci_train = knnmodel.predict(neighbor_idxs_train,
                                                   Survival_train=survival, 
                                                   Censored_train=censored, 
                                                   Survival_test=survival, 
                                                   Censored_test=censored, 
                                                   K=K, 
                                                   Method=Method)
                    if USE_VALID:
                        _, Ci_valid = knnmodel.predict(neighbor_idxs_valid,
                                                   Survival_train=survival, 
                                                   Censored_train=censored, 
                                                   Survival_test=survival_valid, 
                                                   Censored_test=censored_valid, 
                                                   K=K, 
                                                   Method=Method)
                    if not USE_VALID:
                        Ci_valid = 0
                        
                    if MONITOR:
                        print("\t{}\t{}\t{}\t{}".format(\
                                self.EPOCHS_RUN,
                                round(cost_tot, 3), 
                                round(Ci_train, 3),
                                round(Ci_valid, 3)))                                                                       
                    
                    # Update and save                     
                    #==========================================================
                    
                    # update epochs and append costs                     
                    self.EPOCHS_RUN += 1
                    self.Costs_epochLevel_train.append(cost_tot)
                    self.CIs_train.append(Ci_train)
                    self.CIs_valid.append(Ci_valid)
                   
                    # periodically save model
                    #if (self.EPOCHS_RUN % MODEL_SAVE_STEP) == 0:
                    #    _saveTFmodel() 
                    
                    # periodically monitor progress
                    if MONITOR:
                        if (self.EPOCHS_RUN % PLOT_STEP == 0) and \
                            (self.EPOCHS_RUN > 0):
                            _monitorProgress() 
                        
                    # Early stopping
                    #==========================================================

                    if EARLY_STOPPING:
                        # Save snapshot                        
                        Ws[:, :, itir % MODEL_BUFFER] = W_grabbed 
                        Cis.append(Ci_valid)
                        
                        # Stop when overfitting starts to occur
                        if len(Cis) > (2 * MODEL_BUFFER):
                            ci_new = np.mean(Cis[-MODEL_BUFFER:])
                            ci_old = np.mean(Cis[-2*MODEL_BUFFER:-MODEL_BUFFER])        
                    
                            if ci_new < ci_old:
                                snapshot_idx = (itir - MODEL_BUFFER+1) % MODEL_BUFFER
                                W_grabbed = Ws[:, :, snapshot_idx]
                                break
                    
            except KeyboardInterrupt:
                pass
            
            #pUtils.Log_and_print("Finished training model.")
            #pUtils.Log_and_print("Obtaining final results.")            
            
            if MONITOR:
                # save final model
                #_saveTFmodel()
                
                # plot costs
                if EARLY_STOPPING:
                    snapshot = itir - MODEL_BUFFER
                else:
                    snapshot = None    
                _monitorProgress(snapshot_idx=snapshot)
                
                # save learned weights
                np.save(self.RESULTPATH + 'model/' + self.description + \
                        self.timestamp + 'NCA_matrix.npy', W_grabbed)
            
        return W_grabbed

                        
    #%%============================================================================
    # Rank features
    #==============================================================================

    def rankFeats(self, w, fnames, X=None, rank_type = "weights", PLOT=True):
        
        """ ranks features by feature weights or variance after transform"""
        
        print("Ranking features by " + rank_type)
    
        fidx = np.arange(self.D).reshape(self.D, 1)        
        
        w = np.diag(w)
        
        if rank_type == 'weights':
            # rank by feature weight
            ranking_metric = w[:, None]
        elif rank_type == 'stdev':
            assert X is not None
            # rank by variance after transform
            W = np.zeros([self.D, self.D])
            np.fill_diagonal(W, w)
            X = np.dot(X, W)
            ranking_metric = np.std(X, 0).reshape(self.D, 1)
        
        ranking_metric = np.concatenate((fidx, ranking_metric), 1)      
    
        # Plot feature weights/variance
        if PLOT:        
            if self.D <= 500:
                n_plot = ranking_metric.shape[0]
            else:
                n_plot = 500
            self._plotMonitor(ranking_metric[0:n_plot,:], 
                              "feature " + rank_type, 
                              "feature_index", rank_type, 
                              self.RESULTPATH + "plots/" + \
                              self.description + self.timestamp + \
                              "feat_" + rank_type+"_.svg")
        
        # rank features
        
        if rank_type == "weights":
            # sort by absolute weight but keep sign
            ranking = ranking_metric[np.abs(ranking_metric[:,1]).argsort()][::-1]
        elif rank_type == 'stdev':    
            ranking = ranking_metric[ranking_metric[:,1].argsort()][::-1]
        
        fnames_ranked = fnames[np.int32(ranking[:,0])].reshape(self.D, 1)
        fw = ranking[:,1].reshape(self.D, 1) 
        fnames_ranked = np.concatenate((fnames_ranked, fw), 1)
        
        # save results
        
        savename = self.RESULTPATH + "ranks/" + self.description + self.timestamp + \
                    "_" + rank_type + "_ranked.txt"
        with open(savename,'wb') as f:
            np.savetxt(f,fnames_ranked,fmt='%s', delimiter='\t')


    #%%============================================================================
    # Visualization methods
    #==============================================================================
    
    def _plotMonitor(self, arr, title, xlab, ylab, savename, 
                     arr2=None, snapshot_idx=None):
                            
        """ plots cost/other metric to monitor progress """
        
        print("Plotting " + title)
        
        fig, ax = plt.subplots() 
        ax.plot(arr[:,0], arr[:,1], color='b', linewidth=1.5, aa=False)
        if arr2 is not None:
            ax.plot(arr[:,0], arr2, color='r', linewidth=1.5, aa=False)
        if snapshot_idx is not None:
            plt.axvline(x=snapshot_idx, linewidth=1.5, color='r', linestyle='--')
        plt.title(title, fontsize =16, fontweight ='bold')
        plt.xlabel(xlab)
        plt.ylabel(ylab) 
        plt.tight_layout()
        plt.savefig(savename)
        plt.close()

    #==========================================================================    
        
#%% ###########################################################################
#%% ###########################################################################
#%% ###########################################################################
#%% ###########################################################################
