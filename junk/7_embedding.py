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

#%%============================================================================
# Define params
#==============================================================================

base_path = '/home/mohamed/Desktop/CooperLab_Research/KNN_Survival/'
#base_path = '/home/mtageld/Desktop/KNN_Survival/'
result_path = base_path + 'Results/12_21Oct2017/'

sites = ["GBMLGG", "KIPAN"]
dtypes = ["Integ", ] # "Gene"]
methods = ["cumulative-time_TrueNCA_FalsePCA", "non-cumulative_TrueNCA_FalsePCA"]

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

# Fetch accuracies and sort
accuracy_path = specific_path + 'nca/plots/'
accuracy_files = os.listdir(accuracy_path)
accuracy_files = [j for j in accuracy_files if 'valid' in j]
accuracy_files.sort()

#%% 
# Fetch embeddings and plot
#==============================================================================

def isolate_feats(fnames, thresholds):
    
    """
    isolate indices of patients having feature of interest.
    Args:
        fnames - feature names
        thresholds - threshold above which feature is considered present
    Returns:
        is_feat - np array (N, ) indicating no of positive features per patient
    """
    
    feat_idx = [i for i,j in enumerate(fnames) if j in fnames]
    
    is_feat = np.zeros([N,])
    
    for fid, f in enumerate(feat_idx):
        is_feat = is_feat + (Features[:, f] > thresholds[fid])
        
    return is_feat

#%%

# IDH
is_IDHwt = isolate_feats(fnames=("IDH1_Mut", "IDH2_Mut"), thresholds=(0, 0))
is_IDHwt = 1 - np.int32(is_IDHwt > 0)

# 1p19q
is_1p19qCodel = isolate_feats(fnames=("1p_CNVArm", "19q_CNVArm"), thresholds=(0, 0))
is_1p19qCodel = 1 - np.int32(is_1p19qCodel == 2)

# codels and non-codels
IDHmut = 1 - is_IDHwt
NonCodel = 1 - is_1p19qCodel
is_IDHmutNonCodel = np.int32((IDHmut + NonCodel) == 2)
is_IDHmutCodel = np.int32((IDHmut + is_1p19qCodel) == 2)
    
#embed_idx = 16; embed_fname = embedding_files[embed_idx]
for embed_idx, embed_fname in enumerate(embedding_files):

    print("fold {}".format(embed_idx))
    
    # Get embedding
    embedding = np.dot(Features, np.load(embed_path + embed_fname))
    
    # Get accuracy
    ci_valid = np.loadtxt(accuracy_path + accuracy_files[embed_idx])
    
    
    # plot and save
    # -------------------------------------------------------------------------
    
    
    #plt.scatter(embedding[is_IDHwt==0, 0], embedding[is_IDHwt==0, 1], c='b')
    #plt.scatter(embedding[is_IDHmutNonCodel==1, 0], embedding[is_IDHmutNonCodel==1, 1], c='b', alpha=0.5)
    #plt.scatter(embedding[is_IDHmutCodel==1, 0], embedding[is_IDHmutCodel==1, 1], c='g', alpha=0.5)
    
    #plt.scatter(embedding[is_IDHwt==0, 0], embedding[is_IDHwt==0, 1], c='b')
    #plt.scatter(embedding[is_IDHwt==1, 0], embedding[is_IDHwt==1, 1], c='r')
    
    #plt.scatter(embedding[is_1p19qCodel==1, 0], embedding[is_1p19qCodel==1, 1], c='b')
    #plt.scatter(embedding[is_1p19qCodel==0, 0], embedding[is_1p19qCodel==0, 1], c='r')
    
    plt.scatter(embedding[is_1p19qCodel==1, 0], embedding[is_1p19qCodel==1, 1], c='b')
    plt.scatter(embedding[is_1p19qCodel==0, 0], embedding[is_1p19qCodel==0, 1], c='g')
    plt.scatter(embedding[is_IDHwt==1, 0], embedding[is_IDHwt==1, 1], c='r')
    
    #for ptidx in range(N):
    #    
    #    if is_IDHwt[ptidx] == 1:
    #        ptcolor = 'r'
    #    else:
    #        ptcolor = 'b'
    #        
    #    if is_1p19qCodel[ptidx] == 1:
    #        ptmarker = 'o'
    #    else:
    #        ptmarker = '^'
    #    
    #    plt.scatter(embedding[ptidx, 0], embedding[ptidx, 1], c=ptcolor, marker=ptmarker, alpha=0.5)
    
    
    plt.title("ci_valid = {}, n_epochs = {}".format(round(ci_valid[-1], 3), len(ci_valid)), fontsize=16)
    plt.savefig(result_path + '/tmp/' + embed_fname + '.svg')
    plt.close()