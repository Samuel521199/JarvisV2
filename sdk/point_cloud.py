"""Three-dimensional bounds and symmetric PCA without a NumPy runtime."""
import math


def bounds(points):
    lower=[math.inf]*3;upper=[-math.inf]*3;count=0
    for point in points:
        if len(point)!=3 or not all(math.isfinite(v) for v in point):raise ValueError('Finite 3D points required')
        count+=1
        for i in range(3):lower[i]=min(lower[i],point[i]);upper[i]=max(upper[i],point[i])
    if not count:raise ValueError('Empty point cloud')
    return lower,upper


def principal_axes(points):
    """Return centre and ascending orthonormal eigenvectors of sample covariance.

    Jacobi rotations on a symmetric 3x3 matrix avoid a native linear-algebra
    dependency. Repeated eigenvalues describe an inherently ambiguous frame.
    """
    count=len(points)
    if count<2:raise ValueError('PCA requires at least two points')
    centre=tuple(math.fsum(p[i] for p in points)/count for i in range(3))
    cov=[[math.fsum((p[i]-centre[i])*(p[j]-centre[j]) for p in points)/(count-1) for j in range(3)] for i in range(3)]
    if not all(math.isfinite(v) for row in cov for v in row):raise ValueError('Invalid covariance')
    vectors=[[float(i==j) for j in range(3)] for i in range(3)]
    tolerance=max(abs(v) for row in cov for v in row)*1e-14
    for _ in range(64):
        p,q=max(((0,1),(0,2),(1,2)),key=lambda ij:abs(cov[ij[0]][ij[1]]))
        if abs(cov[p][q])<=tolerance:break
        theta=.5*math.atan2(2*cov[p][q],cov[q][q]-cov[p][p]);c=math.cos(theta);s=math.sin(theta)
        app,aqq,apq=cov[p][p],cov[q][q],cov[p][q]
        cov[p][p]=c*c*app-2*c*s*apq+s*s*aqq;cov[q][q]=s*s*app+2*c*s*apq+c*c*aqq
        cov[p][q]=cov[q][p]=0.
        for i in range(3):
            if i not in (p,q):
                aip,aiq=cov[i][p],cov[i][q];cov[i][p]=cov[p][i]=c*aip-s*aiq;cov[i][q]=cov[q][i]=s*aip+c*aiq
            vip,viq=vectors[i][p],vectors[i][q];vectors[i][p]=c*vip-s*viq;vectors[i][q]=s*vip+c*viq
    else:raise ValueError('PCA did not converge')
    axes=[]
    for j in sorted(range(3),key=lambda j:cov[j][j]):
        axis=tuple(vectors[i][j] for i in range(3));pivot=max(range(3),key=lambda i:abs(axis[i]))
        axes.append(tuple(-v for v in axis) if axis[pivot]<0 else axis)
    return centre,axes


def project(points,centre,axes):
    return [tuple(math.fsum((p[i]-centre[i])*axis[i] for i in range(3)) for axis in axes) for p in points]


def reconstruct(centre,axes,coordinates):
    return tuple(centre[i]+math.fsum(axis[i]*v for axis,v in zip(axes,coordinates)) for i in range(3))
