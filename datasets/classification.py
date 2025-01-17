###################################################################################################
#
# Copyright (C) 2018-2020 Maxim Integrated Products, Inc. All Rights Reserved.
#
# Maxim Integrated Products, Inc. Default Copyright Notice:
# https://www.maximintegrated.com/en/aboutus/legal/copyrights.html
#
###################################################################################################
#
# Portions Copyright (c) 2018 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""
Datasets for classifying images
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms, utils
import torchvision
from PIL import Image
import torch
import pandas as pd
import os
from matplotlib import cm
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
from math import comb
import torch.nn.functional as F

from torch.utils.data.sampler import Sampler
import random

import ai8x

# random.seed(1) 
# torch.manual_seed(1)
# np.random.seed(0)
'''
Generic Dataset Class
Parameters:
  img_dir_path - Full path to directory with the images for this dataset.
                 This assumes that the subdirectories contain each class, 
                 only images are in these subdirectories, and that the
                 subdirectory basenames are the desired name of the object class.
                 i.e. dog/dog1.png, cat/cat1.png, etc.
  transform -    Specifies the image format (size, RGB, etc.) and augmentations to use
  subset -       List of indices to sample from if we have a separate validation
                 set that is sampling from the same overall list. For example, the dataset
                 might be [0, 1, 2, 3, 4, 5, 6, 7, 8, 9] but the validation set might be
                 [2, 5, 6] and the train set might be [0, 1, 3, 4, 7, 8, 9]
  get_path -     returns the image file name in addition to the image and label
'''
class ClassificationDataset(Dataset):
    def __init__(self,img_dir_path,transform,subset=None,get_path=False):
        self.img_dir_path = img_dir_path
        self.transform = transform
        self.subset = subset
        self.get_path = get_path

        print(self.img_dir_path)
        
        # collect img classes from dir names
        img_classes = next(os.walk(img_dir_path))[1]
        
        # generate a dictionary to map class names to integers idxs
        self.classes = {img_classes[i] : i for i in range(0, len(img_classes))}
        self.label_dict = {v: k for k, v in self.classes.items()}
        print(self.classes) # use this ordering on synthesized model
        
        # get all training samples/labels by getting absolute paths of the images in each subfolder
        self.imgs = [] # absolute img paths (all images)
        self.labels = [] # integer labels (all labels in corresponding order)

        i = 0 # index into dataset lists

        # iterate through the dataset directory tree
        for idx, path_obj in enumerate(os.walk(img_dir_path)):
            # each execution of this inner loop is for each subdirectory
            if idx > 0: # don't include files in the top folder (subfolders are in the next itertion, idx > 0)
                for file in path_obj[2]: # path_obj[2] is list of files in the object class subdirectories
                    self.imgs.append(os.path.abspath(os.path.join(path_obj[0],file))) # want absolute path
                    self.labels.append(self.classes[os.path.basename(os.path.dirname(self.imgs[i]))]) # get label from directory name
                    i+=1

        # if no subset, just use the whole set
        if subset == None:
            self.subset = [i for i in range(len(self.imgs))]

    # dataset size is determined by the subset size
    def __len__(self):
        return len(self.subset)
    
    # how to get one sample from the dataset
    def __getitem__(self, idx):
        # map the idx to whole set
        idx = self.subset[idx]

        # attempt to load the image at the specified index
        try:
            # load the image
            img = Image.open(self.imgs[idx])

            # if grayscale jsut add channels
            tt = torchvision.transforms.ToTensor()
            tp = torchvision.transforms.ToPILImage()
            tt_img = tt(img)
            if(tt_img.size()[0] != 3):
                img = tp(tt_img.repeat(3, 1, 1))
            
            # apply any transformation
            if self.transform:
                img = self.transform(img)
            
            # get the label
            label = self.labels[idx]
            
            # return the sample (img (tensor)), object class (int), and the path optionally
            if self.get_path:
                return img, label, self.imgs[idx] #os.path.basename(self.imgs[idx])
            else:
                return img, label

        # if the image is invalid, show the exception
        except (ValueError, RuntimeWarning,UserWarning) as e:
            print("Exception: ", e)
            print("Bad Image: ", self.imgs[idx])
            exit()
    
    # Display the results of a forward pass for a random batch of 64 samples
    # if no model passed in, just display a batch with no predictions
    def visualize_batch(self,model=None,device=None):
        # create the dataloader
        batch_size = 64
        data_loader = DataLoader(self,batch_size,shuffle=True)

        # get the first batch
        (imgs, labels, paths) = next(iter(data_loader))
        imgs,labels = imgs.to(device), labels.to(device)
        preds = None

        # check if want to do a forward pass
        if model != None:
            preds = model(imgs)
        
        imgs,labels = imgs.to("cpu"), labels.to("cpu")

        # display the batch in a grid with the img, label, idx
        rows = 8
        cols = 8
        obj_classes = list(self.classes)
        
        fig,ax_array = plt.subplots(rows,cols,figsize=(20,20))
        #fig.subplots_adjust(hspace=0.5)
        plt.subplots_adjust(wspace=0, hspace=0.2)
        num_imgs = 0
        for i in range(rows):
            for j in range(cols):
                if num_imgs == len(imgs):
                    break

                idx = i*rows+j

                # create text labels
                text = str(labels[idx].item()) + " --" + os.path.basename(paths[idx])
                if model != None:
                    text = "GT :" + obj_classes[labels[idx]]  + " P: ",obj_classes[preds[idx].argmax()]#", i=" +str(idxs[idx].item())
                
                ax_array[i,j].imshow((imgs[idx].permute(1, 2, 0)+1)/2) # convert [-128/128, 127/128] to [0.0,1.0]

                ax_array[i,j].set_title(text,color="white")
                ax_array[i,j].set_xticks([])
                ax_array[i,j].set_yticks([])
                num_imgs += 1
            if num_imgs == len(imgs):
                    break
        plt.savefig('plot.png')
        #print(paths)
        #plt.show()

    # def viz_mispredict(self,wrong_samples,wrong_preds,actual_preds,img_names):
    #     wrong_samples,wrong_preds,actual_preds = wrong_samples.to("cpu"), wrong_preds.to("cpu"),actual_preds.to("cpu")
        
    #     # import matplotlib
    #     # matplotlib.use('TkAgg')
    #     obj_classes = list(self.classes)
    #     num_samples = len(wrong_samples)
    #     num_rows = int(np.floor(np.sqrt(num_samples)))

    #     if num_rows > 0:
    #         num_cols = num_samples // num_rows
    #     else:
    #         return
    #     print("num wrong:",num_samples, " num rows:",num_rows, " num cols:",num_cols)

    #     fig,ax_array = plt.subplots(num_rows,num_cols,figsize=(30,30))
    #     fig.subplots_adjust(hspace=1.5)
    #     for i in range(num_rows):
    #         for j in range(num_cols):
    #             idx = i*num_rows+j
    #             sample = wrong_samples[idx]
    #             wrong_pred = wrong_preds[idx]
    #             actual_pred = actual_preds[idx]
    #             # Undo normalization
    #             sample = (sample.permute(1, 2, 0)+1)/2
    #             #text = "L: " + obj_classes[actual_pred.item()]  + " P:",obj_classes[wrong_pred.item()]#", i=" +str(idxs[idx].item())
    #             text = img_names[idx]
                
    #             # for normal forward pass use this line
    #             #ax_array[i,j].imshow(imgs[idx].permute(1, 2, 0))

    #             # for quantized forward pass use this line
    #             #print(imgs[idx].size(),torch.min(imgs[idx]))
    #             try:
    #                 if(ax_array.ndim > 1):
    #                     ax_array[i,j].imshow(sample)
    #                     ax_array[i,j].set_title(text,color="white")
    #                     ax_array[i,j].set_xticks([])
    #                     ax_array[i,j].set_yticks([])
    #             except:
    #                 print("exception")
    #                 print(ax_array.ndim)
    #                 print(sample)
    #                 return
    #     plt.savefig("incorrect.png")


'''
Dataset Class for generating image pairs for few shot domain adaptation
Parameters:
  source_img_dir_path - Full path to directory with the source domain images.
                        This assumes that the subdirectories contain each class, 
                        only images are in these subdirectories, and that the
                        subdirectory basenames are the desired name of the object class.
                        i.e. dog/dog1.png, cat/cat1.png, etc.
  target_img_dir_path - same as source_img_dir_path except for the target domain. The class
                        names should be identical.
  transform -           Specifies the image format (size, RGB, etc.) and augmentations to use
  normalize -           Specifies whether to make the image zero mean, unit variance
'''
class DomainAdaptationPairDataset(Dataset):
    def __init__(self,source_img_dir_path,target_img_dir_path,transform,shot,pair_factor=1,adv_stage=False,source_dataset=None,target_dataset=None,subset=None):
        self.shot = shot
        self.adv_stage = adv_stage
        self.transform = transform
        
        # either take in the source and target datasets as inputs
        if source_dataset != None and target_dataset != None:
            self.source_dataset = source_dataset
            self.target_dataset = target_dataset

        # or create them from the provided paths
        else:
            self.source_img_dir_path = source_img_dir_path
            self.target_img_dir_path = target_img_dir_path

            # print(self.source_img_dir_path)
            # print(self.target_img_dir_path)
            
            # collect img classes from source  dir names
            source_img_classes = next(os.walk(source_img_dir_path))[1]
            target_img_classes = next(os.walk(target_img_dir_path))[1]
            if not source_img_classes == target_img_classes:
                raise AssertionError("source and target classes not the same")
            
            self.source_dataset = ClassificationDataset(source_img_dir_path,transform)
            self.target_dataset = ClassificationDataset(target_img_dir_path,transform)

        # generate an EvenSampler so we can sample each class with equal probability
        self.s_sampler = EvenSampler(self.source_dataset)
        self.t_sampler = EvenSampler(self.target_dataset,shot=shot) # only use a subset of the target dataset based on shot
        # print(f"source_sampler len:{len(self.s_sampler)}, idx_lens: {self.s_sampler.class_idx_lens}")
        # print(f"target_sampler len:{len(self.t_sampler)}, idx_lens: {self.t_sampler.class_idx_lens}")
        # print(f"s_num_classes: {self.s_sampler.num_classes}")
        # print(f"t_num_classes: {self.t_sampler.num_classes}")

        # calculate the number of possible pairs for each set
        # G1: same domain, same class --> each source sample can be paired with each source sample of the same class
        self.num_G1_pairs = sum([comb(self.s_sampler.class_idx_lens[i],2) for i in range(self.s_sampler.num_classes)])
        # G2: different domain, same class --> each target sample can be paired with each source sample of the same class
        self.num_G2_pairs = sum([self.s_sampler.class_idx_lens[i]*self.t_sampler.class_idx_lens[i] for i in range(self.t_sampler.num_classes)])
        # G3: same domain, different class --> each source sample can be paired with any other source sample
        self.num_G3_pairs = comb(len(self.s_sampler.labels),2)
        # G4: different domain, different class --> each target sample can be paired with each source sample of a different class
        self.num_G4_pairs = sum([sum(
                                    [self.s_sampler.class_idx_lens[j]*self.t_sampler.class_idx_lens[i] for j in range(self.s_sampler.num_classes) if i != j]
                                        ) for i in range(self.t_sampler.num_classes)])
        print("Max possible pairs: G1 = ", self.num_G1_pairs, " G2 = ", self.num_G2_pairs, " G3 = ", self.num_G3_pairs, " G4 = ", self.num_G4_pairs)

        # find class with the least possible pairs and use as a reference
        self.min_pairs = min([self.num_G1_pairs, self.num_G2_pairs, self.num_G3_pairs, self.num_G4_pairs])
        self.min_pairs_multiple = pair_factor # use this to reduce amount of pairs for large datasets
        self.min_pairs //= self.min_pairs_multiple

        # set the number of other pairs to be the max # of combos or a multiple of the number of min pairs
        self.num_G1_pairs = min(self.num_G1_pairs,self.min_pairs_multiple*self.min_pairs)
        self.num_G2_pairs = min(self.num_G2_pairs,self.min_pairs_multiple*self.min_pairs)
        self.num_G3_pairs = min(self.num_G3_pairs,self.min_pairs_multiple*self.min_pairs)
        self.num_G4_pairs = min(self.num_G4_pairs,self.min_pairs_multiple*self.min_pairs)

        # now create the sets for these pairs
        self.G1_img_paths = []
        self.G1_labels = []
        self.G2_img_paths = []
        self.G2_labels = []
        self.G3_img_paths = []
        self.G3_labels = []
        self.G4_img_paths = []
        self.G4_labels = []
        
        # these are the indices of the samples in the dataset that we will use to generate the groups
        self.s_sampler_idxs = [i for i in self.s_sampler] # [c0_idx, c1_idx, c2_idx, c0_idx, c2_idx, ...]
        self.t_sampler_idxs = [i for i in self.t_sampler] # [c0_idx, c1_idx, c2_idx, c0_idx, c2_idx, ...]

        # since we can't generate all possible pairs (too many), we must generate a subset of the pairs. To
        # ensure each sample has equal probability of being selected into a pair we split the above indices into
        # partitions and randomly sample from two partitions where a partition is a sequence of items from each class
        # i.e. [c0_idx, c1_idx, c2_idx] is one partition if there are three classes.
        self.num_s_partitions = len(self.s_sampler_idxs)/self.s_sampler.num_classes - 1
        self.num_t_partitions = len(self.t_sampler_idxs)/self.t_sampler.num_classes - 1

        # use the subsets for proper indexing
        s_sub = self.source_dataset.subset
        t_sub = self.target_dataset.subset

        # add G1 pairs
        pair_cnt = 0
        while pair_cnt < self.num_G1_pairs:
            try:
                p1 = random.randint(0,self.num_s_partitions)*self.s_sampler.num_classes # get partition 1 pos
                p2 = random.randint(0,self.num_s_partitions)*self.s_sampler.num_classes # get partition 2 pos
                c = random.randint(0, self.s_sampler.num_classes-1) # get the class to use
                x1_idx,x2_idx = s_sub[self.s_sampler_idxs[p1+c]], s_sub[self.s_sampler_idxs[p2+c]] # using the partition and class, get the sample idxs
                self.G1_img_paths.append((self.source_dataset.imgs[x1_idx],self.source_dataset.imgs[x2_idx]))
                self.G1_labels.append((0,(self.source_dataset.labels[x1_idx],self.source_dataset.labels[x2_idx]))) # class 0, original labels
                pair_cnt += 1
            except IndexError:
                print("p1: ", p1, " p2: ", p2, " c: ", c, " len: ", len(self.s_sampler_idxs), " num p: ", self.num_s_partitions)

        # add G2 pairs
        pair_cnt = 0
        while pair_cnt < self.num_G2_pairs:
            p1 = random.randint(0,self.num_s_partitions)*self.s_sampler.num_classes # get partition 1 pos
            p2 = random.randint(0,self.num_t_partitions)*self.s_sampler.num_classes # get partition 2 pos
            c = random.randint(0, self.s_sampler.num_classes-1) # get the class to use
            x1_idx,x2_idx = s_sub[self.s_sampler_idxs[p1+c]], t_sub[self.t_sampler_idxs[p2+c]] # using the partition and class, get the sample idxs
            self.G2_img_paths.append((self.source_dataset.imgs[x1_idx],self.target_dataset.imgs[x2_idx]))
            if self.adv_stage:
                self.G2_labels.append((0,(self.source_dataset.labels[x1_idx],self.target_dataset.labels[x2_idx]))) # class 0, original labels
            else:
                self.G2_labels.append((1,(self.source_dataset.labels[x1_idx],self.target_dataset.labels[x2_idx]))) # class 1, original labels
            pair_cnt += 1
       
        # add G3 pairs
        pair_cnt = 0
        while pair_cnt < self.num_G3_pairs:
            p1 = random.randint(0,self.num_s_partitions)*self.s_sampler.num_classes # get partition 1 pos
            p2 = random.randint(0,self.num_s_partitions)*self.s_sampler.num_classes # get partition 2 pos
            c1,c2 = random.sample(range(self.s_sampler.num_classes),2) # get the class to use
            x1_idx,x2_idx = s_sub[self.s_sampler_idxs[p1+c1]], s_sub[self.s_sampler_idxs[p2+c2]] # using the partition and class, get the sample idxs
            self.G3_img_paths.append((self.source_dataset.imgs[x1_idx],self.source_dataset.imgs[x2_idx]))
            self.G3_labels.append((2,(self.source_dataset.labels[x1_idx],self.source_dataset.labels[x2_idx]))) # class 0, original labels
            pair_cnt += 1

        # add G4 pairs
        pair_cnt = 0
        while pair_cnt < self.num_G2_pairs:
            p1 = random.randint(0,self.num_s_partitions)*self.s_sampler.num_classes # get partition 1 pos
            p2 = random.randint(0,self.num_t_partitions)*self.t_sampler.num_classes # get partition 2 pos
            c1,c2 = random.sample(range(self.s_sampler.num_classes),2) # get the class to use
            x1_idx,x2_idx = s_sub[self.s_sampler_idxs[p1+c1]], t_sub[self.t_sampler_idxs[p2+c2]] # using the partition and class, get the sample idxs
            self.G4_img_paths.append((self.source_dataset.imgs[x1_idx],self.target_dataset.imgs[x2_idx]))
            if self.adv_stage:
                self.G4_labels.append((2,(self.source_dataset.labels[x1_idx],self.target_dataset.labels[x2_idx]))) # class 0, original labels
            else:
                self.G4_labels.append((3,(self.source_dataset.labels[x1_idx],self.target_dataset.labels[x2_idx]))) # class 1, original labels
            pair_cnt += 1

        # during adversarial training, only feed in G2 and G4 and try to trick into G1 and G3
        if self.adv_stage:
            self.group_imgs = [self.G2_img_paths,self.G4_img_paths]
            self.group_labels = [self.G2_labels,self.G4_labels]
        else:
            self.group_imgs = [self.G1_img_paths,self.G2_img_paths,self.G3_img_paths,self.G4_img_paths]
            self.group_labels = [self.G1_labels,self.G2_labels,self.G3_labels,self.G4_labels]

        # use whole set as subset if no validation split
        if subset == None:
            if self.adv_stage:
                self.subset = [i for i in range(2*self.min_pairs)] # only G2 and G4
            else:
                self.subset = [i for i in range(4*self.min_pairs)] # G1, G2, G3, G4
        else:
            self.subset = subset

    # when we have no validation this is just the whole set
    def __len__(self):
        return len(self.subset)
    
    # how to get one sample from the dataset
    def __getitem__(self, idx):
        # map the idx to the subset
        idx = self.subset[idx]
        if self.adv_stage:
            # map the index into a subindex to a particular group
            group = idx // self.min_pairs
            if group > 1: # in cases where don't divide evenly and exceed max group idx
                group = 1
            
            #sub_idx = random.randint(0,len(self)//2-1)
            sub_idx = idx % self.min_pairs
        else:
            # map the index into a subindex to a particular group
            group = idx // self.min_pairs
            if group > 3: # in cases where don't divide evenly and exceed max group idx
                group = 3
            #sub_idx = random.randint(0,len(self)//4-1)
            sub_idx = idx % self.min_pairs

        # attempt to load the images at the specified index
        try:
            # get paths
            img1_path,img2_path = self.group_imgs[group][sub_idx]
            label = self.group_labels[group][sub_idx]

            # open the imgs
            img1 = Image.open(img1_path)
            img2 = Image.open(img2_path)

            # extend dimensions if grayscale
            tt = torchvision.transforms.ToTensor()
            tp = torchvision.transforms.ToPILImage()
            tt_img = tt(img1)
            if(tt_img.size()[0] != 3):
                img1 = tp(tt_img.repeat(3, 1, 1))

            tt_img = tt(img2)
            if(tt_img.size()[0] != 3):
                img2 = tp(tt_img.repeat(3, 1, 1))
            
            # apply any transformation
            if self.transform:
                img1 = self.transform(img1)
                img2 = self.transform(img2)
            
            # return the samples (img (tensor)), object class (int), and the path optionally
            return img1, img2, label[0], label[1][0], label[1][1]#, os.path.basename(self.imgs[idx])

        # if the image is invalid, show the exception
        except (ValueError, RuntimeWarning,UserWarning, IndexError) as e:
            print("Exception: ", e)
            print("group: ", group, " subindex: ", sub_idx)
            #print("Bad Image: ", self.imgs[idx])
            exit()
    
    # Diaply the results of a forward pass for a random batch of 64 samples
    # if no model passed in, just display a batch with no predictions
    def visualize_batch(self,model=None,device=None):
        #import matplotlib
        #matplotlib.use('TkAgg')

        # create the dataloader
        batch_size = 8
        data_loader = DataLoader(self,batch_size,shuffle=True)

        # get the first batch
        (imgs1, imgs2, pair_labels, imgs1_labels, imgs2_labels) = next(iter(data_loader))
        #(imgs, labels) = next(iter(data_loader))
        
        imgs1, imgs2, pair_labels = imgs1.to(device), imgs2.to(device), pair_labels.to(device)
        preds = None

        # check if want to do a forward pass
        if model != None:
            preds = model((imgs1, imgs2))
        
        imgs1, imgs2, pair_labels, imgs1_labels, imgs2_labels, = imgs1.to("cpu"), imgs2.to("cpu"), pair_labels.to("cpu"), imgs1_labels.to("cpu"), imgs2_labels.to("cpu")
        # display the batch in a grid with the img, label, idx
        rows = 4
        cols = 4
        #obj_classes = list(self.classes)
        
        fig,ax_array = plt.subplots(rows,cols,figsize=(20,20))
        #fig.subplots_adjust(hspace=0.5)
        plt.subplots_adjust(wspace=0, hspace=0)
        
        for i in range(rows):
            for j in range(cols):
                idx = i*rows+j

                # create text labels
                if idx % 2 == 0:
                    text = str(pair_labels[idx // 2].item()) + " " + str(imgs1_labels[idx//2])
                else:
                    text = str(pair_labels[idx // 2].item()) + " " + str(imgs2_labels[idx//2])


                if model != None:
                    text = "GT :" + obj_classes[labels[idx]]  + " P: ",obj_classes[preds[idx].argmax()]#", i=" +str(idxs[idx].item())
                
                # for normal forward pass use this line
                #ax_array[i,j].imshow(imgs[idx].permute(1, 2, 0))

                # for quantized forward pass use this line
                #print(imgs[idx].size(),torch.min(imgs[idx]))
                if idx % 2 == 0:
                    ax_array[i,j].imshow((imgs1[idx // 2].permute(1, 2, 0)+1)/2)
                else:
                    ax_array[i,j].imshow((imgs2[idx // 2].permute(1, 2, 0)+1)/2)

                ax_array[i,j].set_title(text,color="white")
                ax_array[i,j].set_xticks([])
                ax_array[i,j].set_yticks([])
        plt.savefig('plot.png')
        #print(paths)
        #plt.show()


'''
Dataset Class for self-supervised pre-training using SimCLR style training
Parameters:
  img_dir_path - Full path to directory with the images.
                 This assumes that the subdirectories contain each class, 
                 only images are in these subdirectories, and that the
                 subdirectory basenames are the desired name of the object class.
                 i.e. dog/dog1.png, cat/cat1.png, etc.
  transform -    Specifies the image format (size, RGB, etc.) and augmentations to use
'''
class PassDataset(Dataset):
    def __init__(self,img_dir_path,transform):
        self.img_dir_path = img_dir_path
        self.transform = transform
        
        self.imgs = [] # absolute img paths (all images)

        i = 0 # index into dataset lists

        # iterate through the dataset directory tree
        for idx, path_obj in enumerate(os.walk(img_dir_path)):
            # each execution of this inner loop is for each subdirectory
            for file in path_obj[2]: # path_obj[2] is list of files in the object class subdirectories
                self.imgs.append(os.path.abspath(os.path.join(path_obj[0],file))) # want absolute path
                i+=1
        print(img_dir_path)

    # dataset size is number of images
    def __len__(self):
        return len(self.imgs)
    
    # how to get one sample from the dataset
    def __getitem__(self, idx):
        # attempt to load the image at the specified index
        try:
            img = Image.open(self.imgs[idx])

            # if have grayscle image just add channels
            tt = torchvision.transforms.ToTensor()
            tp = torchvision.transforms.ToPILImage()
            tt_img = tt(img)
            if(tt_img.size()[0] != 3):
                img = tp(tt_img.repeat(3, 1, 1))
            
            # apply two transformations to the image
            if self.transform:
                img1 = self.transform(img)
                img2 = self.transform(img)
            
            # return two augmentations of the same image
            return img1,img2

        # if the image is invalid, show the exception
        except (ValueError, RuntimeWarning,UserWarning) as e:
            print("Exception: ", e)
            print("Bad Image: ", self.imgs[idx])
            exit()
    
    # Diaply a random batch of 64 samples
    def visualize_batch(self,device=None):
        batch_size = 32 # --> gets multiplied by 2 since we augment each image
        data_loader = DataLoader(self,batch_size,shuffle=True)

        # get the first batch
        img1,img2 = next(iter(data_loader))

        # display the batch in a grid with the img, label, idx
        rows = 8
        cols = 8
        
        fig,ax_array = plt.subplots(rows,cols,figsize=(20,20))
        #fig.subplots_adjust(hspace=0.5)
        plt.subplots_adjust(wspace=0, hspace=0)
        for i in range(rows):
            for j in range(cols):
                idx = i*rows+j
                
                if idx % 2 == 0:
                    ax_array[i,j].imshow((img1[idx//2].permute(1, 2, 0)+1)/2)
                else:
                    ax_array[i,j].imshow((img2[idx//2].permute(1, 2, 0)+1)/2)
                ax_array[i,j].set_xticks([])
                ax_array[i,j].set_yticks([])
        plt.savefig('plot.png')



# ========================= custom data sampler ===========================

# this class is used to sample items of each class from the dataset equally and randomly
# Example: let's say the dataset is listed like this [C0 (0), C0 (1), C0 (2), C1 (3), C1 (4), C1 (5), C2 (6), C2 (7), C2 (8)],
# the sampler might return the idxs like this: [2 (C0), 3 (C1), 8 (C2), 0 (C0), 4 (C1), 7 (C2), 1 (C0), 5 (C1), 6 (C2)]
class EvenSampler(Sampler):
    def __init__(self, dataset,shot=-1):
        # get the labels as a tensor
        self.labels = torch.Tensor([dataset.labels[idx] for idx in dataset.subset])

        # how many samples from each class to use
        self.shot = shot

        # count the number of classes
        self.num_classes = len(torch.unique(self.labels))

        # get the idxs of each class as a nested list --> [[0,1,2,3],[4,5,6]]
        self.class_idxs = []
        self.remain_class_idxs = []
        self.class_idx_lens = []
        for c in range(self.num_classes):
            # if we specify a shot then only use a subset of the samples per class
            if self.shot != -1:
                idxs = torch.flatten((self.labels == c).nonzero())[0:self.shot]
                remain = torch.flatten((self.labels == c).nonzero())[self.shot:]
                self.remain_class_idxs.append(remain) # need to use this to index into imgs and labels for the valid set
            else:
                idxs = torch.flatten((self.labels == c).nonzero())
            self.class_idxs.append(idxs)
            self.class_idx_lens.append(idxs.size(0))
        self.max_len = max(self.class_idx_lens)
        self.min_len = min(self.class_idx_lens)
        
    def __iter__(self):
        # shuffle the idxs for each class idx list --> [[1,0,2,3],[5,6,4]]
        # also periodically extend the shorter lists --> [[1,0,2,3],[5,6,4,5]]
        # or cuts down the longer lists --> [[1,0,2],[5,6,4]]
        for i,c in enumerate(self.class_idxs):
            rand_idx = torch.randperm(c.size(0))
            shuffled = c[rand_idx]
            self.class_idxs[i] = shuffled
            # added_len = self.max_len-shuffled.size(0)
            # self.class_idxs[i] = torch.cat((shuffled,shuffled[0:added_len]))
            self.class_idxs[i] = shuffled[0:self.min_len]

        # interleave the shuffled lists so that every successive idx is a new class,
        # to get even batches the batch size needs to be a multiple of the number of classes
        # and we need an equal amount per class
        zipped_idxs = torch.stack([t for t in self.class_idxs],dim=1)
        return iter(zipped_idxs.view(zipped_idxs.numel()).tolist())
    
    def __len__(self):
        return len(self.labels)


# =========================== functions to create the dataset ===============================

''' cats and dogs'''
def cats_and_dogs_get_datasets(data, load_train=True, load_test=True,apply_transforms=True):
    (data_dir, args) = data

    train_dataset = None
    test_dataset = None

    # transforms for training
    if load_train and apply_transforms:
        train_transform = transforms.Compose([
            transforms.Resize((128,128)),
            transforms.ColorJitter(brightness=(0.65,1.35),saturation=(0.65,1.35),contrast=(0.65,1.35)),
            transforms.RandomAffine(degrees=20,translate=(0.25,0.25)),
            transforms.RandomHorizontalFlip(),
            transforms.RandomVerticalFlip(),
            #transforms.GaussianBlur(kernel_size=(5, 5), sigma=(0.1, 3)),
            transforms.ToTensor(),
            ai8x.normalize(args=args)
        ])
        train_dataset = ClassificationDataset(os.path.join(data_dir,"train"),train_transform)

    # no data augmentation
    elif load_train and not apply_transforms:
        train_transform = transforms.Compose([
            transforms.Resize((128,128)),
            transforms.ToTensor(),
            ai8x.normalize(args=args)
        ])
        train_dataset = ClassificationDataset(os.path.join(data_dir,"train"),train_transform)

    else:
        train_dataset = None

    # transforms for test, validation --> convert to a valid tensor
    if load_test:
        test_transform = transforms.Compose([
            #transforms.ToPILImage(),
            transforms.Resize((128,128)),
            transforms.ToTensor(),
            ai8x.normalize(args=args)
        ])
        test_dataset = ClassificationDataset(os.path.join(data_dir,"test"),test_transform)

    else:
        test_dataset = None
    
    return train_dataset, test_dataset


''' pairs for domain discriminator '''
def pairs_get_datasets(data,conf,pair_factor):
    (data_dir, args) = data

    train_dataset = None
    val_dataset = None
    test_dataset = None

    train_transform = transforms.Compose([
        transforms.Resize((128,128)),
        #transforms.ToPILImage(),
        #transforms.ColorJitter(brightness=(0.85,1.15),saturation=(0.75,1.25),contrast=(0.75,1.25),hue=(-0.4,0.4)),
        #transforms.RandomGrayscale(0.15),
        #transforms.RandomAffine(degrees=10,translate=(0.27,0.27)),
        #transforms.RandomHorizontalFlip(),
        #transforms.RandomVerticalFlip(),
        #transforms.GaussianBlur(kernel_size=(3, 3), sigma=(0.1, 1.5)),
        transforms.ToTensor(),
        ai8x.normalize(args=args)
    ])
    train_dataset = DomainAdaptationPairDataset(os.path.join(data_dir[0],"train"),os.path.join(data_dir[1],"train"),train_transform,shot=conf.k,pair_factor=pair_factor)
    

    if conf.constrained_validation:
        # split the source training and val sets randomly
        indices = torch.randperm(len(train_dataset))
        val_size = int(len(train_dataset)*conf.validation_split)

        train_dataset = DomainAdaptationPairDataset(os.path.join(data_dir[0],"train"),os.path.join(data_dir[1],"train"),train_transform,shot=conf.k,pair_factor=pair_factor,subset=indices[val_size:])
        val_dataset = DomainAdaptationPairDataset(os.path.join(data_dir[0],"train"),os.path.join(data_dir[1],"train"),train_transform,shot=conf.k,pair_factor=pair_factor,subset=indices[:val_size])
        
    # create independent source and target train-validation sets to sample from
    else:
        assert conf.k >= 3, "k must be >= 3, must have at least one sample per class in the validation set"
        # first create the source training datasets and split into 75-25 train-val
        source_train_dataset = ClassificationDataset(os.path.join(data_dir[0],"train"),train_transform,get_path=True)

        # split the source training and val sets randomly
        indices = torch.randperm(len(source_train_dataset))
        val_size = len(source_train_dataset)//3

        # now create the source train-val sets from the split
        source_train_dataset = ClassificationDataset(os.path.join(data_dir[0],"train"),train_transform,indices[val_size:],True)
        source_val_dataset = ClassificationDataset(os.path.join(data_dir[0],"train"),train_transform,indices[:val_size],True)

        # repeat this process for the target but with desired k

        # first create the target training datasets
        target_train_dataset = ClassificationDataset(os.path.join(data_dir[1],"train"),train_transform,get_path=True)
        sampler = EvenSampler(target_train_dataset,conf.k)
        idxs = [i for i in sampler]
        target_train_dataset = ClassificationDataset(os.path.join(data_dir[1],"train"),train_transform,get_path=True,subset=idxs)

        # split the source training and val sets randomly but giving equal amounts of each class
        # indices = torch.randperm(len(target_train_dataset))
        # val_size = int(len(target_train_dataset)*.25)
        val_k = conf.k//3

        # now create the source train-val sets from the split
        target_train_dataset = ClassificationDataset(os.path.join(data_dir[1],"train"),train_transform,idxs[sampler.num_classes*val_k:],True)
        target_val_dataset = ClassificationDataset(os.path.join(data_dir[1],"train"),train_transform,idxs[:sampler.num_classes*val_k],True)

        labels = [target_val_dataset.labels[l] for l in idxs[:sampler.num_classes*val_k]]
        # print(f"val_k: {val_k} idxs: {idxs[:sampler.num_classes*val_k]} labels: {labels}")
        # target_val_dataset.visualize_batch()
        

        # finally create the pairs datasets
        train_dataset = DomainAdaptationPairDataset(None,None,train_transform,shot=conf.k-val_k,pair_factor=pair_factor,source_dataset=source_train_dataset,target_dataset=target_train_dataset)
        val_dataset = DomainAdaptationPairDataset(None,None,train_transform,shot=val_k,pair_factor=pair_factor,source_dataset=source_val_dataset,target_dataset=target_val_dataset)
    
    return train_dataset, val_dataset


''' pairs for domain discriminator in the adverserial stage, need to change labels'''
def pairs_get_datasets_c(data,conf,pair_factor):
    (data_dir, args) = data

    train_dataset = None
    val_dataset = None

    train_transform = transforms.Compose([
        transforms.Resize((128,128)),
        #transforms.ToPILImage(),
        #transforms.ColorJitter(brightness=(0.85,1.15),saturation=(0.75,1.25),contrast=(0.75,1.25),hue=(-0.4,0.4)),
        #transforms.RandomGrayscale(0.15),
        #transforms.RandomAffine(degrees=10,translate=(0.27,0.27)),
        #transforms.RandomHorizontalFlip(),
        #transforms.RandomVerticalFlip(),
        #transforms.GaussianBlur(kernel_size=(3, 3), sigma=(0.1, 1.5)),
        transforms.ToTensor(),
        ai8x.normalize(args=args)
    ])
    train_dataset = DomainAdaptationPairDataset(os.path.join(data_dir[0],"train"),os.path.join(data_dir[1],"train"),train_transform,shot=conf.k,pair_factor=pair_factor,adv_stage=True)
    

    if conf.constrained_validation:
        # split the source training and val sets randomly
        indices = torch.randperm(len(train_dataset))
        val_size = int(len(train_dataset)*conf.validation_split)

        train_dataset = DomainAdaptationPairDataset(os.path.join(data_dir[0],"train"),os.path.join(data_dir[1],"train"),train_transform,shot=conf.k,pair_factor=pair_factor,subset=indices[val_size:],adv_stage=True)
        val_dataset = DomainAdaptationPairDataset(os.path.join(data_dir[0],"train"),os.path.join(data_dir[1],"train"),train_transform,shot=conf.k,pair_factor=pair_factor,subset=indices[:val_size],adv_stage=True)
        
    # create independent source and target train-validation sets to sample from
    else:
        assert conf.k >= 3, "k must be >= 3, must have at least one sample per class in the validation set"
        # first create the source training datasets and split into 75-25 train-val
        source_train_dataset = ClassificationDataset(os.path.join(data_dir[0],"train"),train_transform,get_path=True)

        # split the source training and val sets randomly
        indices = torch.randperm(len(source_train_dataset))
        val_size = len(source_train_dataset)//3

        # now create the source train-val sets from the split
        source_train_dataset = ClassificationDataset(os.path.join(data_dir[0],"train"),train_transform,indices[val_size:],True)
        source_val_dataset = ClassificationDataset(os.path.join(data_dir[0],"train"),train_transform,indices[:val_size],True)

        # repeat this process for the target but with desired k

        # first create the target training datasets
        target_train_dataset = ClassificationDataset(os.path.join(data_dir[1],"train"),train_transform,get_path=True)
        sampler = EvenSampler(target_train_dataset,conf.k)
        idxs = [i for i in sampler]
        target_train_dataset = ClassificationDataset(os.path.join(data_dir[1],"train"),train_transform,get_path=True,subset=idxs)

        # split the source training and val sets randomly but giving equal amounts of each class
        # indices = torch.randperm(len(target_train_dataset))
        # val_size = int(len(target_train_dataset)*.25)
        val_k = conf.k//3

        # now create the source train-val sets from the split
        target_train_dataset = ClassificationDataset(os.path.join(data_dir[1],"train"),train_transform,idxs[sampler.num_classes*val_k:],True)
        target_val_dataset = ClassificationDataset(os.path.join(data_dir[1],"train"),train_transform,idxs[:sampler.num_classes*val_k],True)

        labels = [target_val_dataset.labels[l] for l in idxs[:sampler.num_classes*val_k]]
        # print(f"val_k: {val_k} idxs: {idxs[:sampler.num_classes*val_k]} labels: {labels}")
        # target_val_dataset.visualize_batch()

        flat_list = [x for xs in sampler.remain_class_idxs for x in xs]
        val_dataset = ClassificationDataset(os.path.join(data_dir[1],"train"),train_transform,get_path=True,subset=flat_list)
        

        # finally create the pairs datasets
        train_dataset = DomainAdaptationPairDataset(None,None,train_transform,shot=conf.k-val_k,pair_factor=pair_factor,source_dataset=source_train_dataset,target_dataset=target_train_dataset,adv_stage=True)
        #val_dataset = DomainAdaptationPairDataset(None,None,train_transform,shot=val_k,pair_factor=pair_factor,source_dataset=source_val_dataset,target_dataset=target_val_dataset,adv_stage=True)
    
    return train_dataset, val_dataset



''' get the office5 dataset '''
def office5_get_datasets(data, load_train=True, load_val=True, load_test=True, validation_split=0.1, fix_aug=None, deterministic=None):
    (data_dir, args) = data

    train_dataset = None
    val_dataset = None
    test_dataset = None
    seed = fix_aug
    # transforms for training
    if load_train:
        train_transform = transforms.Compose([
            transforms.Resize((128,128)),
            #transforms.ToPILImage(),
            transforms.ColorJitter(brightness=(0.85,1.15),saturation=(0.75,1.25),contrast=(0.75,1.25),hue=(-0.4,0.4)),
            transforms.RandomGrayscale(0.15),
            transforms.RandomAffine(degrees=10,translate=(0.27,0.27)),
            transforms.RandomHorizontalFlip(),
            #transforms.RandomVerticalFlip(),
            transforms.GaussianBlur(kernel_size=(3, 3), sigma=(0.1, 1.5)),
            transforms.ToTensor(),
            ai8x.normalize(args=args)
        ])
        train_dataset = ClassificationDataset(os.path.join(data_dir,"train"),train_transform,get_path=True)

        # create a validation set with no augmentations
        if load_val:
            val_transform = transforms.Compose([
                #transforms.ToPILImage(),
                transforms.Resize((128,128)),
                transforms.ToTensor(),
                ai8x.normalize(args=args)
            ])

            # split the training and val sets randomly
            indices = torch.randperm(len(train_dataset))
            val_size = int(len(train_dataset)*validation_split)

            # if aug not fixed then will be different each execution
            if not deterministic:
                if fix_aug != None:
                    random.seed(fix_aug) 
                    torch.manual_seed(fix_aug)
                else:
                    seed = np.random.randint(2147483647)
                    random.seed(seed) 
                    torch.manual_seed(seed)

            train_dataset = ClassificationDataset(os.path.join(data_dir,"train"),train_transform,indices[val_size:],True)
            val_dataset = ClassificationDataset(os.path.join(data_dir,"train"),val_transform,indices[:val_size],True)

    # transforms for test --> convert to a valid tensor
    if load_test:
        test_transform = transforms.Compose([
            #transforms.ToPILImage(),
            transforms.Resize((128,128)),
            transforms.ToTensor(),
            ai8x.normalize(args=args)
        ])
        test_dataset = ClassificationDataset(os.path.join(data_dir,"test"),test_transform,None,True)
    
    return train_dataset, val_dataset, test_dataset, seed



''' get the PASS dataset'''
def pass_get_datasets(data, load_train=True, load_test=False,apply_transforms=True):
    (data_dir, args) = data

    train_dataset = None
    test_dataset = None

    # transforms for training
    if load_train and apply_transforms:
        train_transform = transforms.Compose([
            transforms.RandomResizedCrop(128),
            transforms.ColorJitter(brightness=(0.85,1.15),saturation=(0.85,1.15),contrast=(0.85,1.15),hue=(-0.1,0.1)),
            transforms.RandomGrayscale(0.25),
            #transforms.RandomAffine(degrees=180,translate=(0.15,0.15)),
            transforms.RandomHorizontalFlip(),
            #transforms.RandomVerticalFlip(),
            transforms.ToTensor(),
            ai8x.normalize(args=args)
        ])
        train_dataset = PassDataset(os.path.join(data_dir,"train"),train_transform)

    elif load_train and not apply_transforms:
        train_transform = transforms.Compose([
            transforms.Resize((128,128)),
            transforms.ToTensor(),
            ai8x.normalize(args=args)
        ])
        train_dataset = PassDataset(os.path.join(data_dir,"train"),train_transform)

    else:
        train_dataset = None

    # transforms for test, validatio --> convert to a valid tensor
    if load_test:
        test_transform = transforms.Compose([
            transforms.Resize((128,128)),
            transforms.ToTensor(),
            ai8x.normalize(args=args)
        ])
        test_dataset = PassDataset(os.path.join(data_dir,"test"),test_transform)

    else:
        test_dataset = None
    
    return train_dataset, test_dataset


''' get the office5 dataset '''
def asl_get_datasets(data, load_train=True, load_val=True, load_test=True, validation_split=0.1, fix_aug=None, deterministic=None):
    (data_dir, args) = data

    train_dataset = None
    val_dataset = None
    test_dataset = None
    seed = fix_aug
    # transforms for training
    if load_train:
        train_transform = transforms.Compose([
            transforms.Resize((128,128)),
            #transforms.ToPILImage(),
            transforms.ColorJitter(brightness=(0.85,1.15),saturation=(0.75,1.25),contrast=(0.75,1.25),hue=(-0.4,0.4)),
            transforms.RandomGrayscale(0.15),
            transforms.RandomAffine(degrees=5,translate=(0.1,0.1)),
            #transforms.RandomHorizontalFlip(),
            #transforms.RandomVerticalFlip(),
            transforms.GaussianBlur(kernel_size=(3, 3), sigma=(0.1, 1.5)),
            transforms.ToTensor(),
            ai8x.normalize(args=args)
        ])
        train_dataset = ClassificationDataset(os.path.join(data_dir,"train"),train_transform,get_path=True)

        # create a validation set with no augmentations
        if load_val:
            val_transform = transforms.Compose([
                #transforms.ToPILImage(),
                transforms.Resize((128,128)),
                transforms.ToTensor(),
                ai8x.normalize(args=args)
            ])

            # split the training and val sets randomly
            indices = torch.randperm(len(train_dataset))
            val_size = int(len(train_dataset)*validation_split)

            # if aug not fixed then will be different each execution
            if not deterministic:
                if fix_aug != None:
                    random.seed(fix_aug) 
                    torch.manual_seed(fix_aug)
                else:
                    seed = np.random.randint(2147483647)
                    random.seed(seed) 
                    torch.manual_seed(seed)

            train_dataset = ClassificationDataset(os.path.join(data_dir,"train"),train_transform,indices[val_size:],True)
            val_dataset = ClassificationDataset(os.path.join(data_dir,"train"),val_transform,indices[:val_size],True)

    # transforms for test --> convert to a valid tensor
    if load_test:
        test_transform = transforms.Compose([
            #transforms.ToPILImage(),
            transforms.Resize((128,128)),
            transforms.ToTensor(),
            ai8x.normalize(args=args)
        ])
        test_dataset = ClassificationDataset(os.path.join(data_dir,"test"),test_transform,None,True)
    
    return train_dataset, val_dataset, test_dataset, seed


def set_deterministic_settings():
    random.seed(0)
    np.random.seed(0)
    torch.manual_seed(0)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False

    def seed_worker(worker_id):
        worker_seed = 0
        np.random.seed(0)
        random.seed(0)

    g = torch.Generator()
    g.manual_seed(0)

    return seed_worker