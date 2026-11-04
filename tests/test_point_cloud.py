import math
import unittest
from sdk.point_cloud import bounds,principal_axes,project,reconstruct


class PointCloud(unittest.TestCase):
    def test_rotated_asymmetric_covariance_matches_independent_numpy_oracle(self):
        import numpy as np
        rng=np.random.default_rng(44)
        for scale in ([1,2,5],[.001,.03,1],[1,1,1],[1,2,0]):
            rotation,_=np.linalg.qr(rng.normal(size=(3,3)))
            points=(rng.normal(size=(201,3))*scale)@rotation.T+[2,-3,9]
            centre,axes=principal_axes(points.tolist());values,expected=np.linalg.eigh(np.cov(points.T))
            np.testing.assert_allclose(centre,points.mean(0),atol=1e-13)
            covariance=np.cov(points.T)
            for axis,value in zip(axes,values):np.testing.assert_allclose(covariance@axis,np.array(axis)*value,atol=1e-12)
            basis=np.array(axes);np.testing.assert_allclose(basis@basis.T,np.eye(3),atol=1e-13)
            local=project(points.tolist(),centre,axes)
            np.testing.assert_allclose([reconstruct(centre,axes,p) for p in local],points,atol=1e-12)
            lo,hi=bounds(iter(points.tolist()));np.testing.assert_allclose(lo,points.min(0));np.testing.assert_allclose(hi,points.max(0))

    def test_degenerate_cloud_and_invalid_samples(self):
        self.assertEqual(principal_axes([(1,1,1)]*4)[0],(1,1,1))
        for cloud in ([],[(0,0,0)]):
            with self.assertRaises(ValueError):principal_axes(cloud)
        for cloud in ([],[(float('nan'),0,0)],[(1,2)]):
            with self.assertRaises(ValueError):bounds(cloud)
