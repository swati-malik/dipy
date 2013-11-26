"""
=====================================================
Using the RESTORE algorithm for robust tensor fitting
=====================================================

The diffusion tensor model takes into account certain kinds of noise (thermal),
but not other kinds, such as 'physiological' noise. For example, if a subject
moves during the acquisition of one of the diffusion-weighted samples, this
might have a substantial effect on the parameters of the tensor fit calculated
in all voxels in the brain for that subject. One of the pernicious consequences
of this is that it can lead to wrong interepertation of group differences. For
example, some groups of participants (e.g. young children, patient groups,
etc.) are particularly prone to motion and differences in tensor parameters and
derived statistics (such as FA) due to motion would be confounded with actual
differences in the physical properties of the white matter.

One of the strategies to deal with this problem is to apply an automatic method
for detecting outliers in the data, excluding these outliers and refitting the
model without the presence of these outliers. This is often referred to as
"robust model fitting". One of the common algorithms for robust tensor fitting
is called RESTORE, and was first proposed by Chang et al. [1]_.

In the following example, we will demonstrate how to use RESTORE on a simulated
data-set, which we will corrupt by adding intermittent noise.

We start by importing a few of the libraries we will use. ``Numpy`` for numeric
computation: 

"""

import numpy as np

"""
``nibabel`` is for loading imaging datasets
"""

import nibabel as nib

"""
The module ``dipy.reconst.dti`` contains the implementation of tensor fitting,
including an implementation of the RESTORE algorithm.
"""

import dipy.reconst.dti as dti
reload(dti)

"""
``dipy.data`` is used for small datasets that we use in tests and examples.
"""

import dipy.data as dpd

"""

``dipy.viz.fvtk`` is used for 3D visualization and matplotlib for 2D
visualizations:

"""
import dipy.viz.fvtk as fvtk
import matplotlib.pyplot as plt

"""
If needed, the fetch_stanford_hardi function will download the raw dMRI dataset
of a single subject. The size of this dataset is 87 MBytes. You only need to
fetch once. 
"""

dpd.fetch_stanford_hardi()
img, gtab = dpd.read_stanford_hardi()

"""
We initialize a DTI model class instance using the gradient table used in the
measurement. Per default, dti.Tensor model will use a weighted least-squares
algorithm (described in [2]_) to fit the parameters of the model. We initialize
this model as a baseline for comparison of noise-corrupted models:
"""

dti_wls = dti.TensorModel(gtab)

"""
For the purpose of this example, we will focus on the data from a limited
ROI surrounding the Corpus Callosum. We define that ROI as the following indices:
"""

roi_idx = (slice(32,50), slice(70,80), slice(38,39))

"""
And use them to index into the data:
"""

data = img.get_data()[roi_idx]

"""
This data is not very noisy and we will artificially corrupt it to simulate the
effects of 'physiological' noise, such as subject motion. But first, let's
establish a baseline, using the data as it is:   
"""

fit_wls = dti_wls.fit(data)

fa1 = fit_wls.fa
evals1 = fit_wls.evals
evecs1 = fit_wls.evecs
cfa1 = dti.color_fa(fa1, evecs1)
sphere = dpd.get_sphere('symmetric724')

"""
We visualize the ODFs in the ROI using fvtk:
"""

r = fvtk.ren()
fvtk.add(r, fvtk.tensor(evals1, evecs1, cfa1, sphere))
print('Saving illustration as tensor_ellipsoids_wls.png')
fvtk.record(r, n_frames=1, out_path='tensor_ellipsoids_wls.png',
            size=(1200, 1200))

"""
.. figure:: tensor_ellipsoids_wls.png
   :align: center

   **Tensor Ellipsoids**.
"""

fvtk.clear(r)

"""
Next, we corrupt the data with some noise. To simulate a subject that moves
intermittently, we will replace a few of the images with a very low signal
"""

noisy_data = np.copy(data)
noisy_idx = slice(-10, None)  # The last 10 volumes are corrupted
noisy_data[..., noisy_idx] = 1.0

"""
We use the same model to fit this noisy data
"""

fit_wls_noisy = dti_wls.fit(noisy_data)
fa2 = fit_wls_noisy.fa
evals2 = fit_wls_noisy.evals
evecs2 = fit_wls_noisy.evecs
cfa2 = dti.color_fa(fa2, evecs2)

r = fvtk.ren()
fvtk.add(r, fvtk.tensor(evals2, evecs2, cfa2, sphere))
print('Saving illustration as tensor_ellipsoids_wls_noisy.png')
fvtk.record(r, n_frames=1, out_path='tensor_ellipsoids_wls_noisy.png',
            size=(600, 600))


"""
In places where the tensor model is particularly sensitive to noise, the
resulting ODF field will be distorted 

.. figure:: tensor_ellipsoids_wls_noisy.png
   :align: center

   **Tensor Ellipsoids from noisy data**.

To estimate the parameters from the noisy data using RESTORE, we need to
estimate what would be a reasonable amount of noise to expect in the
measurement. There are two common ways of doing that. The first is to look at
the variance in the signal in parts of the volume outside of the brain, or in
the ventricles, where the signal is expected to be identical regardless of
the direction of diffusion weighting. If several non diffusion-weighted volumes
were acquired, another way is to calculate the variance in these volumes.
"""

mean_std = np.mean(np.std(data[..., gtab.b0s_mask], -1))

"""
This estimate is usually based on a small sample, and is thus a bit biased (for
a proof of that fact, see the following derivation_.)


.. _derivation: http://nbviewer.ipython.org/4287207

Therefore, we apply a small sample correction. In this case, the bias is rather
small: 
"""

from scipy.special import gamma
n = np.sum(gtab.b0s_mask)
bias = mean_std*(1. - np.sqrt(2. / (n-1)) * (gamma(n / 2.) / gamma((n-1) / 2.)))
sigma = mean_std + bias

"""

This estimate of the standard deviation will be used by the RESTORE algorithm
to identify the outliers in each voxel and is given as an input when
initializing the TensorModel object:
"""

dti_restore = dti.TensorModel(gtab,fit_method='RESTORE', sigma=sigma)
fit_restore_noisy = dti_restore.fit(noisy_data)
fa3 = fit_restore_noisy.fa
evals3 = fit_restore_noisy.evals
evecs3 = fit_restore_noisy.evecs
cfa3 = dti.color_fa(fa3, evecs3)

r = fvtk.ren()
fvtk.add(r, fvtk.tensor(evals3, evecs3, cfa3, sphere))
print('Saving illustration as tensor_ellipsoids_restore_noisy.png')
fvtk.record(r, n_frames=1, out_path='tensor_ellipsoids_restore_noisy.png',
            size=(600, 600))

"""

.. figure:: tensor_ellipsoids_restore_noisy.png
   :align: center

   **Tensor Ellipsoids from noisy data recovered with RESTORE**.

To convince ourselves further that this did the right thing, we will compare
the distribution of FA in this region relative to the baseline, using the
RESTORE estimate and the WLS estimate
"""

fig_hist, ax = plt.subplots(1)
ax.hist(np.ravel(fa2), color='b', histtype='step', label='WLS')
ax.hist(np.ravel(fa3), color='r', histtype='step', label='RESTORE')
ax.hist(np.ravel(fa1), color='g', histtype='step', label='Original')
ax.set_xlabel('Fractional Anisotropy')
ax.set_ylabel('Count')
plt.legend()
fig_hist.savefig('dti_fa_distributions.png')

"""

.. figure:: dti_fa_distributions.png
   :align: center


This demonstrates that RESTORE can recover a distribution of FA that more
closely resembles the baseline distribution of the noiseless signal.


References
----------

.. [1] Chang, L-C, Jones, DK and Pierpaoli, C (2005). RESTORE: robust estimation
       of tensors by outlier rejection. MRM, 53: 1088-95. 

.. [2] Chung, SW., Lu, Y., Henry, R.G., 2006. Comparison of bootstrap
       approaches for estimation of uncertainties of DTI parameters.
       NeuroImage 33, 531-541.

.. include:: ../links_names.inc


"""
