# -*- coding: utf-8 -*-
"""
Created on Fri Oct 21 19:02:31 2016

@author: dingning
"""
from __future__ import division
import os
from PIL import Image
import numpy as np
from scipy import sqrt, pi, arctan2, io
from scipy.ndimage import uniform_filter
from sklearn.linear_model import Lasso
from math import floor


def load_boxes(data_type = 'train'):
    '''
    load the ground truth ground truth boxes coordinates from .mat file
    ---------------------------------------------------------------------------
    INPUT:
        data_type: 'train' or 'test'  by default is 'train'
    OUTPUT:
        a dict with all the ground truth bounding boxes coordinates
        key: a string of filename    ex: 'image_0122.png'
        value: a numpy array of boungding boxes
    ---------------------------------------------------------------------------
    '''
    file_path = 'data/bounding_boxes/bounding_boxes_lfpw_' + data_type + 'set.mat'
    assert os.path.exists(file_path)
    x = io.loadmat(file_path)['bounding_boxes'][0]
    x = [x[0][0] for x in x]
    return {x[i][0][0]:x[i][1][0] for i in range(len(x))}
    
    
def load_landmarks(image_name):
    '''
    load the landmarks coordinates from .pts file
    ---------------------------------------------------------------------------
    INPUT:
        image_name: a string without extension   ex: 'image_0122'
    OUTPUT:
        a numpy array containing all the points
    ---------------------------------------------------------------------------
    '''   
    file_path = 'data/trainset/pts/' + image_name + '.pts'  
    assert os.path.exists(file_path)
    with open(file_path) as f: rows = [rows.strip() for rows in f]
    coords_set = [point.split() for point in rows[rows.index('{') + 1:rows.index('}')]]
    return np.array([list([float(point) for point in coords]) for coords in coords_set])
    
    
    
    
def get_image_path_list(data_type='train'):
    '''
    get a list containing all the paths of images in the trainset
    ---------------------------------------------------------------------------
    INPUT:
        data_type: 'train' or 'test'  by default is 'train'
    OUTPUT:
        a list with all the images' paths
    ---------------------------------------------------------------------------
    '''
    folder_path = 'data/' + data_type + 'set/png'
    assert os.path.exists(folder_path)
    assert os.path.isdir(folder_path)
    return os.listdir(folder_path)


def compute_new_bbox(image_size,bbox,expand_rate = 0.1):
    '''
    compute the expanded bbox
    a robust function to expand the crop image bbox even the original bbox is
    around the border of the image
    ---------------------------------------------------------------------------
    INPUT:
        image_size: a tuple   ex: (height,width)
        bbox: the ground_truth bounding boxes  ex:[x0,y0,x1,y1]
        expand_rate: the rate to expand the bbox  by default is 0.1
    OUTPUT:
        new bbox: ex:[x0,y0,x1,y1]
    '''
    x_size,y_size = image_size
    bx0,by0,bx1,by1 = bbox
    bw = by1 - by0
    bh = bx1 - bx0
    if bw > bh:
        delta = expand_rate * bw
        if by1 + delta > y_size:
            nby1 = y_size
        else:
            nby1 = int(floor(by1 + delta))
        if by0 - delta < 0:
            nby0 = 0
        else:
            nby0 = int(floor(by0 - delta))
        new_w = nby1 - nby0
        delta_h = (new_w - bh) / 2
        if bx0 - delta_h < 0:
            nbx0 = 0
        else:
            nbx0 = int(floor(bx0 - delta_h))
        if bx1 + delta_h > x_size:
            nbx1 = x_size
        else:
            nbx1 = int(floor(bx1 + delta_h))
    else:
        delta = expand_rate * bh
        if bx1 + delta > x_size:
            nbx1 = x_size
        else:
            nbx1 = int(floor(bx1 + delta))
        if bx0 - delta < 0:
            nbx0 = 0
        else:
            nbx0 = int(floor(bx0 - delta))
        new_h = nbx1 - nbx0
        delta_w = (new_h - bw) / 2
        if by0 - delta_w < 0:
            nby0 = 0
        else:
            nby0 = int(floor(by0 - delta_w))
        if by1 + delta_w > y_size:
            nby1 = y_size
        else:
            nby1 = int(floor(by1 + delta_w))
    return nbx0,nby0,nbx1,nby1
    
def crop_and_resize_image(image_name,bbox,new_size=(100,100),data_type = 'train'):
    '''
    crop and resize the image given the ground truth bounding boxes
    also, compute the new coordinates according to transformation
    ---------------------------------------------------------------------------
    INPUT:
        image_name: a string without extension  ex: 'image_0007'
        bbox: the ground_truth bounding boxes  ex:[x0,y0,x1,y1]
        new_size: the size used by the resize function
        data_type: 'train' or 'test'
    OUTPUT:
        grey: a numpy array of grey image after crop and resize
        landmarks: new landmarks accordance with new image
    ---------------------------------------------------------------------------
    '''
    image_path = 'data/' + data_type + 'set/png/' + image_name + '.png'
    assert os.path.exists(image_path)
    im = Image.open(image_path)
    
    #compute the new bbox and the crop and resize the image
    bbox = compute_new_bbox(im.size,bbox)
    im_crop = im.crop(bbox)
    im_resize = im_crop.resize(new_size)
    grey = im_resize.convert('L')
    
    #compute the new landmarks according to transformation procedure
    landmarks = load_landmarks(image_name)
    landmarks -= bbox[:2]
    landmarks = landmarks * im_resize.size / im_crop.size    
    
    return np.array(grey),landmarks.astype(int)




def hog(image, xys, orientations=9, pixels_per_cell=3,cells_per_side=1, cells_per_block=1):
    '''
    Given a grey image in numpy array and a vector of sequence of coordinates,
    return the ndarray of hog feature vectors extract from given locations
    ---------------------------------------------------------------------------
    INPUT:
        image: grey image, numpy array, 8-bit
        xys: coordinates, numpy array, float
        orientations: the number that the orientations are divided, int
        pixels_per_cell: int
        cells_per_side: int
        cells_per_block: int
    OUTPUT:
        features: ndarray of all the features extracted from locations in xy
    ---------------------------------------------------------------------------
    '''
    image = np.atleast_2d(image)    
    if image.ndim > 3: raise ValueError("Currently only supports grey-level images")


    '''normalisation'''
    image = sqrt(image)
    
    
    '''---------compute the gradients of the input grey image---------------'''
    gx = np.zeros(image.shape)
    gy = np.zeros(image.shape)
    gx[:, :-1] = np.diff(image, n=1, axis=1)
    gy[:-1, :] = np.diff(image, n=1, axis=0)
    '''---------------------------------------------------------------------'''
    
    
    '''----------compute the magnitude and orientation of gradients---------'''
    magnitude = sqrt(gx ** 2 + gy ** 2)
    orientation = arctan2(gy, (gx + 1e-15)) * (180 / pi) + 180
    '''---------------------------------------------------------------------'''

    #just for convinients, make the variables shorter
    r = pixels_per_cell * cells_per_side
    pc = pixels_per_cell
    
    
    '''--------------compute the orientation histogram----------------------'''
    orientation_histogram = np.zeros((len(xys), cells_per_side*2, cells_per_side*2, orientations))    
    for j in range(len(xys)):        
        x, y = xys[j]
        for i in range(orientations):
            # classify the orientation of the gradients
            temp_ori = np.where(orientation <= 180 / orientations * (i + 1) * 2,
                                orientation, 0)
            temp_ori = np.where(orientation > 180 / orientations * i * 2,
                                temp_ori, 0)
            # select magnitudes for those orientations
            cond2 = temp_ori > 0
            temp_mag = np.where(cond2, magnitude, 0)
        
            orientation_histogram[j,:,:,i] = uniform_filter(temp_mag, size=pc)[x-r+pc/2:x+r:pc, y-r+pc/2:y+r:pc].T
    '''---------------------------------------------------------------------'''
    
    
    '''----------------compute the block normalization----------------------'''
    n_blocks = cells_per_side * 2 - cells_per_block + 1
    cb = cells_per_block
    normalised_blocks = np.zeros((len(xys), n_blocks, n_blocks, cb, cb, orientations))
    eps = 1e-5
    for i in range(len(xys)):
        for x in range(n_blocks):
            for y in range(n_blocks):
                block = orientation_histogram[i,x:x + cb, y:y + cb, :]            
                normalised_blocks[i, x, y, :] = block / sqrt(block.sum() ** 2 + eps)
    '''---------------------------------------------------------------------'''
    
    return normalised_blocks.ravel()



def train(data, initial_x, N = 5, alpha = 0.1):
    '''
    the standard SDM training function
    ---------------------------------------------------------------------------
    INPUT:
        data: a list containing all the images and true shape coordinates
        initial_x: a numpy array containing initial estimated shape coordinates
        N: number of train iteration
        alpha: the coefficient of L1 regularization of Lasso Linear Regression
    OUTPUT:
        regressors: a list containing a sequence of (R,b)
    ---------------------------------------------------------------------------
    '''
    x = initial_x
    true_x = data[:,1]
    regressors = []
    
    for i in range(N):
        
        '''计算当前坐标与真实坐标之差 '''
        delta_x = true_x - x
        
        
        '''根据当前坐标计算特征矩阵'''
        H = []
        for j in range(len(data)):
            H.append(hog(data[j][0],data[j][1]))
        H = np.array(H)
        
        
        '''
        根据线性最小二乘或回归分析求解(R,b)
        '''
        reg = Lasso(alpha=alpha)
        reg.fit(H,delta_x.ravel())  
        regressors.append([reg.coef_,reg.intercept_])        
                
        '''计算更新之后的坐标x'''
        x = x + reg.coef_ * H + reg.intercept_
        
    return regressors






'''
if __name__=='__main__':

    
    by run this python file, we could get a list named Data
    Data containing 811 tuples and each tuple holds two numpy array containing images and marks
    
    bbox = load_ground_truth_data()
    image_list = get_data_path_list()
    Data = []
    for path in image_list:Data.append(crop_image(path[:10], list(bbox[path])))    
'''