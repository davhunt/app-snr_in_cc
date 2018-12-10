#!/usr/bin/env python

"""

=============================================
SNR estimation for Diffusion-Weighted Images
=============================================

Computing the Signal-to-Noise-Ratio (SNR) of DW images is still an open
question, as SNR depends on the white matter structure of interest as well as
the gradient direction corresponding to each DWI.

In classical MRI, SNR can be defined as the ratio of the mean of the signal
divided by the standard deviation of the underlying Gaussian noise, that is
$SNR = mean(signal) / std(noise)$. The noise standard deviation can be computed
from the background in any of the DW images. How do we compute the mean of the
signal, and what signal?

The strategy here is to compute a 'worst-case' SNR for DWI. Several white
matter structures such as the corpus callosum (CC), corticospinal tract (CST),
or the superior longitudinal fasciculus (SLF) can be easily identified from the
colored-FA (CFA) map. In this example, we will use voxels from the CC, which
have the characteristic of being highly red in the CFA map since they are
mainly oriented in the left-right direction. We know that the DW image closest
to the X-direction will be the one with the most attenuated diffusion signal.
This is the strategy adopted in several recent papers (see [Descoteaux2011]_
and [Jones2013]_). It gives a good indication of the quality of the DWI data.

First, we compute the tensor model in a brain mask (see the :ref:`reconst_dti`
example for further explanations).

"""

import logging
import shutil
import numpy as np
import nibabel as nib
import sys
import os
#import matplotlib.pyplot as plt
from scipy.ndimage.morphology import binary_dilation

#from dipy.data import fetch_stanford_hardi, read_stanford_hardi
from dipy.io import read_bvals_bvecs
from dipy.core.gradients import gradient_table
from dipy.segment.mask import median_otsu
from dipy.reconst.dti import TensorModel
        
from dipy.segment.mask import segment_from_cfa
from dipy.segment.mask import bounding_box



"""
``shutil`` Will be used for sample file manipulation.
"""

from dipy.workflows.workflow import Workflow

"""
``Workflow`` is the base class that will be extended to create our workflow.
"""


class SNRinCCFlow(Workflow):
    
    @classmethod
    def get_short_name(cls):
        return 'snrincc'
    
    def run(self, data_file, data_bvals, data_bvecs, mask=None, bbox_threshold=(0.6, 1, 0, 0.1, 0, 0.1), out_dir = '', out_file='product.json'):
    #def run(self, data_file, out_dir = '', bounding_box_threshold=0, out_file = 'product.json'):
        """
        Parameters
        ----------
        data_file : string
            Path to the input files directory. This path may contain wildcards to
            process multiple inputs at once.
        data_bvals : string
            Path of bvals.
        data_bvecs : string
            Path of bvecs.
        mask : string, optional
            Path of mask if needed. (default None)
        bbox_threshold : string, optional
            for ex. [0.6,1,0,0.1,0,0.1], converted to a tuple; threshold for bounding box. (default (0.6, 1, 0, 0.1, 0, 0.1))
        out_dir : string, optional
            Where the resulting file will be saved. (default '')
        out_file : string, optional
            Name of the result file to be saved. (default 'product.json')
        """
        print bbox_threshold
        print type(bbox_threshold)
        if bbox_threshold != (0.6, 1, 0, 0.1, 0, 0.1):
            b = bbox_threshold.replace("[","")
            b = b.replace("]","")
            b = b.split(",")
            for i in range(len(b)):
                b[i] = float(b[i])
            bbox_threshold = tuple(b)

        io_it = self.get_io_iterator()
        
        for data_path, data_bvals_path, data_bvecs_path, out_path in io_it:
        #for data_path, out_path in io_it:

            print data_path
            print data_bvals_path
            print data_bvecs_path
            print out_path
            #img = nib.load('{0}dwi.nii.gz'.format(in_file))
            #bvals, bvecs = read_bvals_bvecs('{0}dwi.bvals'.format(in_file), '{0}dwi.bvecs'.format(in_file))

            
            #img = nib.load('{0}'.format(in_file))
            #bvals, bvecs = read_bvals_bvecs('{1}'.format(in_file), '{2}'.format(in_file))
            #gtab = gradient_table(bvals, bvecs)
            
            
            img = nib.load('{0}'.format(data_path))
            bvals, bvecs = read_bvals_bvecs('{0}'.format(data_bvals_path), '{0}'.format(data_bvecs_path))
            gtab = gradient_table(bvals, bvecs)
            
            data = img.get_data()
            affine = img.affine

            if mask == None:
                logging.info('Computing brain mask...')
                b0_mask, mask = median_otsu(data)
                    #else:
            #                mask = mask

            logging.info('Computing tensors...')
            tenmodel = TensorModel(gtab)
            tensorfit = tenmodel.fit(data, mask=mask)

            """Next, we set our red-green-blue thresholds to (0.6, 1) in the x axis
            and (0, 0.1) in the y and z axes respectively.
            These values work well in practice to isolate the very RED voxels of the cfa map.

            Then, as assurance, we want just RED voxels in the CC (there could be
            noisy red voxels around the brain mask and we don't want those). Unless the brain
            acquisition was badly aligned, the CC is always close to the mid-sagittal slice.

            The following lines perform these two operations and then saves the computed mask.
            """

            logging.info('Computing worst-case/best-case SNR using the corpus callosum...')

            threshold = bbox_threshold #make parameter
            CC_box = np.zeros_like(data[..., 0]) #check 4 4-d

            mins, maxs = bounding_box(mask)
            mins = np.array(mins)
            maxs = np.array(maxs)
            diff = (maxs - mins) // 4
            bounds_min = mins + diff
            bounds_max = maxs - diff

            CC_box[bounds_min[0]:bounds_max[0],
                   bounds_min[1]:bounds_max[1],
                   bounds_min[2]:bounds_max[2]] = 1

            mask_cc_part, cfa = segment_from_cfa(tensorfit, CC_box, threshold,
                                                 return_cfa=True)

            cfa_img = nib.Nifti1Image((cfa*255).astype(np.uint8), affine)
            mask_cc_part_img = nib.Nifti1Image(mask_cc_part.astype(np.uint8), affine)
            nib.save(mask_cc_part_img, 'cc.nii.gz')

            #region = 40
            # fig = plt.figure('Corpus callosum segmentation')
            # plt.subplot(1, 2, 1)
            # plt.title("Corpus callosum (CC)")
            # plt.axis('off')
            # red = cfa[..., 0]
            # plt.imshow(np.rot90(red[region, ...]))

            # plt.subplot(1, 2, 2)
            # plt.title("CC mask used for SNR computation")
            # plt.axis('off')
            # plt.imshow(np.rot90(mask_cc_part[region, ...]))
            #fig.savefig("CC_segmentation.png", bbox_inches='tight')

            """Now that we are happy with our crude CC mask that selected voxels in the x-direction,
            we can use all the voxels to estimate the mean signal in this region.

            """

            mean_signal = np.mean(data[mask_cc_part], axis=0)

            """Now, we need a good background estimation. We will re-use the brain mask
            computed before and invert it to catch the outside of the brain. This could
            also be determined manually with a ROI in the background.
            [Warning: Certain MR manufacturers mask out the outside of the brain with 0's.
            One thus has to be careful how the noise ROI is defined].
            """

            mask_noise = binary_dilation(mask, iterations=10)
            mask_noise[..., :mask_noise.shape[-1]//2] = 1
            mask_noise = ~mask_noise
            mask_noise_img = nib.Nifti1Image(mask_noise.astype(np.uint8), affine)
            #nib.save(mask_noise_img, 'mask_noise.nii.gz')

            noise_std = np.std(data[mask_noise, :])
            #logging.info('Noise standard deviation sigma= ' + noise_std)

            """We can now compute the SNR for each DWI. For example, report SNR
            for DW images with gradient direction that lies the closest to
            the X, Y and Z axes.
            """

            # Exclude null bvecs from the search
            idx = np.sum(gtab.bvecs, axis=-1) == 0
            gtab.bvecs[idx] = np.inf
            axis_X = np.argmin(np.sum((gtab.bvecs-np.array([1, 0, 0]))**2, axis=-1))
            axis_Y = np.argmin(np.sum((gtab.bvecs-np.array([0, 1, 0]))**2, axis=-1))
            axis_Z = np.argmin(np.sum((gtab.bvecs-np.array([0, 0, 1]))**2, axis=-1))

            SNR_output = []
            for direction in [0, axis_X, axis_Y, axis_Z]:
                SNR = mean_signal[direction]/noise_std
                if direction == 0 :
                    logging.info("SNR for the b=0 image is :" + str(SNR))
                else :
                    logging.info("SNR for direction" + str(direction) + " " + str(gtab.bvecs[direction]) + "is :" + str(SNR))
                SNR_output.append(SNR)
            #write output data to product.json
            SNR_output = str(SNR_output[0]) + ' ' + str(SNR_output[1]) + ' ' + str(SNR_output[2]) + ' ' + str(SNR_output[3])
            """SNR for the b=0 image is : ''42.0695455758''"""
            """SNR for direction 58  [ 0.98875  0.1177  -0.09229] is : ''5.46995373635''"""
            """SNR for direction 57  [-0.05039  0.99871  0.0054406] is : ''23.9329492871''"""
            """SNR for direction 126 [-0.11825  -0.039925  0.99218 ] is : ''23.9965694823''"""

            """

            Since the CC is aligned with the X axis, the lowest SNR is for that gradient
            direction. In comparison, the DW images in the perpendical Y and Z axes have a
            high SNR. The b0 still exhibits the highest SNR, since there is no signal
            attenuation.

            Hence, we can say the Stanford diffusion data has a 'worst-case' SNR of
            approximately 5, a 'best-case' SNR of approximately 24, and a SNR of 42 on the
            b0 image.

            """
            
            """
            References
            ----------

            .. [Descoteaux2011] Descoteaux, M., Deriche, R., Le Bihan, D., Mangin, J.-F.,
            and Poupon, C. Multiple q-shell diffusion propagator imaging. Medical Image
            Analysis, 15(4), 603, 2011.
           
           .. [Jones2013] Jones, D. K., Knosche, T. R., & Turner, R. White Matter
            Integrity, Fiber Count, and Other Fallacies: The Dos and Don'ts of Diffusion
            MRI. NeuroImage, 73, 239, 2013.
           
            """

            with open(os.path.join(out_dir,out_file), 'w') as myfile: #os.path.join
                
                myfile.write(SNR_output)  #json.dump / json.dumps?

#            shutil.copy('{0}product.json'.format(in_file), '/Users/davidhunt/app-snr_in_cc')

# from dipy.workflows.my_workflow import SNRinCCFlow

from dipy.workflows.flow_runner import run_flow


if __name__ == "__main__":
    run_flow(SNRinCCFlow())  #in another file -- nipy/dipy/tree/master/bin
#create new folder/python file "stats"


# remove comments
# clone dipy (fork?), make branch, push to my github, pull request