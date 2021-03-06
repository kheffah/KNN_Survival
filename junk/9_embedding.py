# -*- coding: utf-8 -*-
"""
Created on Mon Oct 23 23:57:35 2017

@author: mohamed
"""

import sys
sys.path.append('/home/mohamed/Desktop/CooperLab_Research/KNN_Survival/Codes')
#sys.path.append('/home/mtageld/Desktop/KNN_Survival/Codes')

import os
import numpy as np
import matplotlib.pylab as plt
from scipy.io import loadmat
from scipy.stats import spearmanr

#%%============================================================================
# Define params
#==============================================================================

base_path = '/home/mohamed/Desktop/CooperLab_Research/KNN_Survival/'
#base_path = '/home/mtageld/Desktop/KNN_Survival/'
result_path = base_path + 'Results/12_21Oct2017/'

sites = ["GBMLGG", "KIPAN"]
dtypes = ["Integ", ] # "Gene"]
methods = ["cumulative-time_TrueNCA_FalsePCA", "non-cumulative_TrueNCA_FalsePCA"]

n_top_folds = 30
pval_thresh = 0.01
n_feats_to_plot = 10

site = sites[0]
dtype = dtypes[0]
method = methods[0]

#%% 
# Get feature files
#==============================================================================

dpath = base_path + "Data/SingleCancerDatasets/"+ site+"/" + \
        site +"_"+ dtype+"_Preprocessed.mat"

print("Loading data.")
Data = loadmat(dpath)
Features = Data[dtype + '_X'].copy()
N = Features.shape[0]
P = Features.shape[1]
Survival = Data['Survival'].reshape([N,])
Censored = Data['Censored'].reshape([N,])
fnames = Data[dtype + '_Symbs']
fnames = [j.split(' ')[0] for j in fnames]
Data = None

#%% 
# Get result files
#==============================================================================

specific_path = result_path + method + '/' + site + '_' + dtype + '_' + '/'

# Fetch embeddings and sort
embed_path = specific_path + 'nca/model/'
embedding_files = os.listdir(embed_path)
embedding_files = [j for j in embedding_files if '.npy' in j]
embedding_files.sort()
embedding_files = np.array(embedding_files)

# Fetch accuracies and sort all by accuracy
accuracies = np.loadtxt(specific_path + site + '_' + dtype + '_testing_Ci.txt')
top_folds = np.argsort(accuracies)[::-1][0:n_top_folds]

# keep top folds
accuracies = accuracies[top_folds]
embedding_files = embedding_files[top_folds]

#sys.exit()

#%%============================================================================
# Itirate through embeddings and get cluster separations
#==============================================================================

threshold = 0 # Z-scored

NC_deltas = np.zeros((len(embedding_files), P))

#embed_idx = 16; embed_fname = embedding_files[embed_idx]
for embed_idx, embed_fname in enumerate(embedding_files):
    
    print("fold {}".format(embed_idx))

    # Get embedding
    embedding = np.dot(Features, np.load(embed_path + embed_fname))
    
    # Itirate through features and get cluster separation
    for fidx in range(P):
    
        # Get cluster separation
        feat_is_present = 0 + (Features[:, fidx] > threshold)
        
        # Get distance across various neighborhood components
        NC_delta = 0
        for ncidx in range(embedding.shape[1]):
            delta = np.mean(embedding[feat_is_present==0, ncidx]) - \
                    np.mean(embedding[feat_is_present==1, ncidx])    
            NC_delta = NC_delta + delta**2
        
        NC_deltas[embed_idx, fidx] = np.sqrt(NC_delta)

#%%============================================================================
# Rank features by correlation between their separation and accuracy
#==============================================================================

rhos = np.zeros((P, ))
pvals = np.zeros((P, ))

# find spearman correlations
for fidx in range(P):
    corr = spearmanr(accuracies, NC_deltas[:, fidx])
    rhos[fidx] = corr[0]
    pvals[fidx] = corr[1]

rhos_signif = rhos
rhos_signif[pvals > pval_thresh] = 0

top_feat_idxs = np.argsort(rhos_signif)[::-1]
top_feat_names = np.array(fnames)[top_feat_idxs]

#%%============================================================================
# Visualize top features
#==============================================================================

#fidx = top_feat_idxs[0]
for rank, fidx in enumerate(top_feat_idxs[0:n_feats_to_plot]):
    
    
    fname_string = fnames[fidx].replace('_', ' ')[0: 15]
    
    print("rank " + str(rank) + ": plotting " + fname_string)


    # Visualize feature distribution in best embedding
    # -------------------------------------------------------------------------

    # fetch embedding with highest separation
    embedding = np.dot(Features, np.load(embed_path + embedding_files[np.argmax(NC_deltas[:, fidx])]))
    
    feat_is_present = 0 + (Features[:, fidx] > threshold)
    
    plt.scatter(embedding[feat_is_present==0, 0], embedding[feat_is_present==0, 1], c='b')
    plt.scatter(embedding[feat_is_present==1, 0], embedding[feat_is_present==1, 1], c='r')
    plt.title(fname_string + ": testing Ci= {}, NC delta= {}".\
               format(round(accuracies[0], 3), 
                      round(NC_deltas[0, fidx], 3)), 
               fontsize=16)
    plt.xlabel("NC1", fontsize=14)
    plt.ylabel("NC2", fontsize=14)
    plt.savefig(result_path + '/tmp/' + str(rank) + '_' + fnames[fidx] + '_clusters.svg')
    plt.close()
    

    # Visualize correlation between cluster separation and accuracy
    #--------------------------------------------------------------------------
    
    # scatter points
    plt.scatter(accuracies, NC_deltas[:, fidx])
    
    # plot line of best fit
    slope, intercept = np.polyfit(accuracies, NC_deltas[:, fidx], deg=1)
    abline_values = [slope * i + intercept for i in accuracies]
    plt.plot(accuracies, abline_values, 'b--')
    
    pval_string = round(pvals[fidx], 3)
    if pval_string == 0:
        pval_string = '<0.001'
    else:
        pval_string = '= ' + str(pval_string)
    
    plt.title(fname_string + ": spRho= {}, p {}".\
              format(round(rhos[fidx], 3), pval_string), fontsize=16)
    plt.xlabel("Testing C-index", fontsize=14)
    plt.ylabel("cluster separation", fontsize=14)
    plt.savefig(result_path + '/tmp/' + str(rank) + '_' + fnames[fidx] + '_corr.svg')
    plt.close()