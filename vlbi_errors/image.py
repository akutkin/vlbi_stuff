import os
import math
import numpy as np
import astropy.io.fits as pf
from scipy import signal
from utils import (create_grid, create_mask, mas_to_rad, v_round,
                   get_fits_image_info_from_hdulist, get_hdu_from_hdulist)
from model import Model
from beam import CleanBeam
from skimage.feature import register_translation
import matplotlib.pyplot as plt
# from matplotlib.patches import Ellipse

try:
    import pylab
except ImportError:
    pylab = None


# TODO: Implement plotting w/o coordinates - in pixels. Use pixel numbers as
# coordinates.
# TODO: Make possible use ``blc`` & ``trc`` in mas.
def plot(contours=None, colors=None, vectors=None, vectors_values=None, x=None,
         y=None, blc=None, trc=None, cmap='hsv', abs_levels=None,
         rel_levels=None, min_abs_level=None, min_rel_level=None, k=2., vinc=2.,
         show_beam=False, beam_corner='ll', beam=None, contours_mask=None,
         colors_mask=None, vectors_mask=None, plot_title=None, color_clim=None,
         outfile=None, outdir=None, ext='png', close=False, slice_points=None,
         beam_place='ll', colorbar_label=None, show=True):
    """
    Plot image(s).

    :param contours: (optional)
        Numpy 2D array (possibly masked) that should be plotted using contours.
    :param colors: (optional)
        Numpy 2D array (possibly masked) that should be plotted using colors.
    :param vectors: (optional)
        Numpy 2D array (possibly masked) that should be plotted using vectors.
    :param vectors_values: (optional)
        Numpy 2D array (possibly masked) that should be used as vector's lengths
        when plotting ``vectors`` array.
    :param x: (optional)
        Iterable of x-coordinates. It's length must be comparable to that part
        of image to display. If ``None`` then don't plot coordinates - just
        pixel numbers. (default=``None``)
    :param y: (optional)
        Iterable of y-coordinates. It's length must be comparable to that part
        of image to display. If ``None`` then don't plot coordinates - just
        pixel numbers. (default=``None``)
    :param blc: (optional)
        Iterable of two values for Bottom Left Corner (in pixels). Must be in
        range ``[1, image_size]``. If ``None`` then use ``(1, 1)``. (default:
        ``None``)
    :param trc: (optional)
        Iterable of two values for Top Right Corner (in pixels). Must be in
        range ``[1, image_size]``. If ``None`` then use ``(image_size,
        image_size)``. (default: ``None``)
    :param cmap: (optional)
        Colormap to use for plotting colors. Available color maps could be
        printed using ``sorted(m for m in plt.cm.datad if not
        m.endswith("_r"))`` where ``plt`` is imported ``matplotlib.pyplot``.
        For further details on plotting available colormaps see
        http://matplotlib.org/1.2.1/examples/pylab_examples/show_colormaps.html.
        (default: ``hsv``)
    :param abs_levels: (optional)
        Iterable of absolute levels. If ``None`` then construct levels in other
        way. (default: ``None``)
    :param min_abs_level: (optional)
        Values of minimal absolute level. Used with conjunction of ``factor``
        argument for building sequence of absolute levels. If ``None`` then
        construct levels in other way. (default: ``None``)
    :param rel_levels: (optional)
        Iterable of relative levels. If ``None`` then construct levels in other
        way. (default: ``None``)
    :param min_rel_level: (optional)
        Values of minimal relative level. Used with conjunction of ``factor``
        argument for building sequence of relative levels. If ``None`` then
        construct levels in other way. (default: ``None``)
    :param k: (optional)
        Factor of incrementation for levels. (default: ``2.0``)
    :param show_beam: (optional)
        Convertable to boolean. Should we plot beam in corner? (default:
        ``False``)
    :param beam_corner: (optional)
        Place (corner) where to plot beam on map. One of ('ll', 'lr', 'ul',
        'ur') where first letter means lower/upper and second - left/right.
        (default: ``ll'')
    :param beam: (optional)
        If ``show_beam`` is True then ``beam`` should be iterable of major axis,
        minor axis [mas] and beam positional angle [deg]. If no coordinates are
        supplied then beam parameters must be in pixels.
    :param colorbar_label: (optional)
        String to label colorbar. If ``None`` then don't label. (default:
        ``None``)
    :param slice_points: (optional)
        Iterable of 2 coordinates (``y``, ``x``) [mas] to plot slice. If
        ``None`` then don't plot slice. (default: ``None``)

    :note:
        ``blc`` & ``trc`` are AIPS-like (from 1 to ``imsize``). Internally
        converted to python-like zero-indexing. If none are specified then use
        default values. All images plotted must have the same shape.
    """

    image = None
    if contours is not None:
        image = contours
    elif colors is not None and image is None:
        image = colors
    elif vectors is not None and image is None:
        image = vectors

    if image is None:
        raise Exception("No images to plot!")
    if x is None:
        x = np.arange(image.shape[0])
        factor_x = 1
    else:
        factor_x = 1. / mas_to_rad
    if y is None:
        y = np.arange(image.shape[1])
        factor_y = 1
    else:
        factor_y = 1. / mas_to_rad

    # Set BLC & TRC
    blc = blc or (1, 1,)
    trc = trc or image.shape
    # Use ``-1`` because user expect AIPS-like behaivior of ``blc`` & ``trc``
    x_slice = slice(blc[1] - 1, trc[1], None)
    y_slice = slice(blc[0] - 1, trc[0],  None)

    # Create coordinates
    imsize_x = x_slice.stop - x_slice.start
    imsize_y = y_slice.stop - y_slice.start
    # In mas (if ``x`` & ``y`` were supplied in rad) or in pixels (if no ``x`` &
    # ``y`` were supplied)
    x_ = x[x_slice] * factor_x
    y_ = y[y_slice] * factor_y
    # With this coordinates are plotted as in Zhenya's map
    # x_ *= -1.
    # y_ *= -1.
    # Coordinates for plotting
    x = np.linspace(x_[0], x_[-1], imsize_x)
    y = np.linspace(y_[0], y_[-1], imsize_y)

    # Optionally mask arrays
    if contours is not None and contours_mask is not None:
        contours = np.ma.array(contours, mask=contours_mask)
    if colors is not None and colors_mask is not None:
        colors = np.ma.array(colors, mask=colors_mask)
    if vectors is not None and vectors_mask is not None:
        vectors = np.ma.array(vectors, mask=vectors_mask)

    # Actually plotting
    fig = plt.figure()
    ax = fig.add_axes([0.1, 0.1, 0.8, 0.8])
    ax.set_xlabel('RA, [mas]')
    ax.set_ylabel('DEC, [mas]')

    # Plot contours
    if contours is not None:
        # If no absolute levels are supplied then construct them
        if abs_levels is None:
            print "constructing absolute levels for contours..."
            max_level = contours[x_slice, y_slice].max()
            # from given relative levels
            if rel_levels is not None:
                print "from relative levels..."
                # Build levels (``pyplot.contour`` takes only absolute values)
                abs_levels = [-max_level] + [max_level * i for i in rel_levels]
                # If given only min_abs_level & increment factor ``k``
            # from given minimal absolute level
            elif min_abs_level is not None:
                print "from minimal absolute level..."
                n_max = int(math.ceil(math.log(max_level / min_abs_level, k)))
            # from given minimal relative level
            elif min_rel_level is not None:
                print "from minimal relative level..."
                min_abs_level = min_rel_level * max_level / 100.
                n_max = int(math.ceil(math.log(max_level / min_abs_level, k)))
            abs_levels = [-min_abs_level] + [min_abs_level * k ** i for i in
                                             range(n_max)]
            print "Constructed absolute levels are: ", abs_levels
        co = ax.contour(y, x, contours[x_slice, y_slice], abs_levels,
                        colors='k')
    if colors is not None:
        im = ax.imshow(colors[x_slice, y_slice], interpolation='none',
                       origin='lower', extent=[y[0], y[-1], x[0], x[-1]],
                       cmap=plt.get_cmap('hsv'), clim=color_clim)
    if vectors is not None:
        if vectors_values is not None:
            # TODO: Does "-" sign because of RA increases to the left actually?
            # VLBIers do count angles from North to negative RA.
            u = -vectors_values[x_slice, y_slice] * np.sin(vectors[x_slice,
                                                                   y_slice])
            v = vectors_values[x_slice, y_slice] * np.cos(vectors[x_slice,
                                                                  y_slice])
        else:
            u = -np.sin(vectors[x_slice, y_slice])
            v = np.cos(vectors[x_slice, y_slice])

        if vectors_mask is not None:
            u = np.ma.array(u, mask=vectors_mask[x_slice, y_slice])
            v = np.ma.array(v, mask=vectors_mask[x_slice, y_slice])
        vec = ax.quiver(y[::vinc], x[::vinc], u[::vinc, ::vinc],
                        v[::vinc, ::vinc], angles='uv',
                        units='xy', headwidth=0., headlength=0., scale=0.005,
                        width=0.05, headaxislength=0.)

    if slice_points is not None:
        ax.plot([slice_points[0][0], slice_points[1][0]],
                [slice_points[0][1], slice_points[1][1]])

    if plot_title:
        title = ax.set_title(plot_title, fontsize='large')
    # Add colorbar if plotting colors
    if colors is not None:
        colorbar_ax = fig.add_axes([0.80, 0.10, 0.05, 0.80])
        cb = fig.colorbar(im, cax=colorbar_ax)
        if colorbar_label is not None:
            cb.set_label(colorbar_label)

    from matplotlib.patches import Ellipse
    e_height = beam[0]
    e_width = beam[1]
    r_min = e_height / 2
    if beam_place == 'lr':
        y_c = y[0] + r_min
        x_c = x[-1] - r_min
    elif beam_place == 'll':
        if y[0] > 0:
            y_c = y[0] - r_min
        else:
            y_c = y[0] + r_min
        if x[0] > 0:
            x_c = x[0] - r_min
        else:
            x_c = x[0] + r_min
    elif beam_place == 'ul':
        y_c = y[-1] - r_min
        x_c = x[0] + r_min
    elif beam_place == 'ur':
        y_c = y[-1] - r_min
        x_c = x[-1] - r_min
    else:
        raise Exception

    # FIXME: check how ``bpa`` should be plotted
    e = Ellipse((y_c, x_c), e_width, e_height, angle=beam[2], edgecolor='black',
                facecolor='green', alpha=0.3)
    ax.add_patch(e)

    # Saving output
    if outfile:
        if outdir is None:
            outdir = '.'
        # If the directory does not exist, create it
        if not os.path.exists(outdir):
            os.makedirs(outdir)

        path = os.path.join(outdir, outfile)
        print "Saving to {}.{}".format(path, ext)
        plt.savefig("{}.{}".format(path, ext), bbox_inches='tight', dpi=200)

    if show:
        fig.show()
    if close:
        plt.close()


class BasicImage(object):
    """
    Image class that implements basic image functionality that physical scale
    free.
    """
    def __init__(self):
        self.imsize = None
        self._image = None

    def _construct(self, **kwargs):
        try:
            self.imsize = kwargs["imsize"]
        except KeyError:
            raise Exception
        self._image = np.zeros(self.imsize, dtype=float)

    def from_hdulist(self, hdulist):
        image_params = get_fits_image_info_from_hdulist(hdulist)
        self._construct(**image_params)
        pr_hdu = get_hdu_from_hdulist(hdulist)
        self.image = pr_hdu.data.squeeze()

    def from_fits(self, fname):
        hdulist = pf.open(fname)
        self.from_hdulist(hdulist)

    @property
    def image(self):
        """
        Shorthand for image array.
        """
        return self._image

    @image.setter
    def image(self, image):
        if isinstance(image, Image):
            if self == image:
                self._image = image.image.copy()
            else:
                raise Exception("Images have incompatible parameters!")
        # If ``image`` is array-like
        else:
            image = np.atleast_2d(image).copy()
            if not self.imsize == np.shape(image):
                raise Exception("Images have incompatible parameters!")
            self._image = image

    def __eq__(self, other):
        """
        Compares current instance of ``BasicImage`` class with other instance.
        """
        return self.imsize == other.imsize

    def __ne__(self, image):
        """
        Compares current instance of ``BasicImage`` class with other instance.
        """
        return self.imsize != image.imsize

    def __add__(self, image):
        """
        Sums current instance of ``BasicImage`` class with other instance.
        """
        if self == image:
            self.image += image.image
        else:
            raise Exception("Different image parameters")
        return self

    def __mul__(self, other):
        """
        Multiply current instance of ``BasicImage`` class with other instance or
        some number.
        """
        if isinstance(other, BasicImage):
            if self == other:
                self.image *= other.image
            else:
                raise Exception("Different image parameters")
        else:
            self.image *= other
        return self

    def __sub__(self, other):
        """
        Substruct from current instance of ``BasicImage`` class other instance
        or some number.
        """
        if isinstance(other, BasicImage):
            if self == other:
                self._image -= other.image
            else:
                raise Exception("Different image parameters")
        else:
            self._image -= other
        return self

    def __div__(self, other):
        """
        Divide current instance of ``BasicImage`` class on other instance or
        some number.
        """
        if isinstance(other, BasicImage):
            if self == other:
                self.image /= other.image
            else:
                raise Exception("Different image parameters")
        else:
            self.image /= other
        return self

    # TODO: In subclasses pixels got sizes so one can use physical sizes as
    # ``region`` parameters. Subclasses should extend this method.
    def rms(self, region=None, do_plot=False, **hist_kwargs):
        """
        Method that calculate rms for image region.

        :param region: (optional)
            Region to include in rms calculation. Or (blc[0], blc[1], trc[0],
            trc[1],) or (center[0], center[1], r, None,). If ``None`` then use
            all image in rms calculation. Default ``None``.
        :param do_plot: (optional)
            Plot histogram of image values? (default: ``False``)
        :param hist_kwargs: (optional)
            Any keyword arguments that get passed to ``plt.hist``.
        :return:
            rms value.
        """
        mask = np.zeros(self.image.shape, dtype=bool)
        if region is not None:
            mask = create_mask(self.image.shape, region)
        masked_image = np.ma.array(self.image, mask=~mask)

        if do_plot:
            plt.hist(masked_image.compressed(), **hist_kwargs)

        return np.ma.std(masked_image.ravel())

    def convolve(self, image):
        """
        Convolve ``Image`` array with image-like instance or 2D array-like.

        :param image:
            Instance of ``BasicImage`` or 2D array-like.
        """
        try:
            to_convolve = image.image
        except AttributeError:
            to_convolve = np.atleast_2d(image)
        return signal.fftconvolve(self._image, to_convolve, mode='same')

    # TODO: Implement Rayleigh (Rice) distributed noise for stokes I
    # FIXME: This is uncorrelated noise - that is too simple model
    def add_noise(self, std, df=None):
        size = self.imsize[0] * self.imsize[1]
        if df is None:
            rvs = np.random.normal(loc=0., scale=std, size=size)
        else:
            raise NotImplementedError
        rvs = rvs.reshape(self.imsize)
        self._image += rvs

    # TODO: Should i compare images before?
    # TODO: Implement several regions to include for each image
    # TODO: Implement masking clean components with ``mask_cc`` parameter
    def cross_correlate(self, image, region1=None, region2=None,
                        upsample_factor=100, extended_output=False,
                        mask_cc=False):
        """
        Cross-correlates current instance of ``Image`` with another instance
        using phase correlation.

        :param image:
            Instance of image class.
        :param region1: (optional)
            Region to EXCLUDE in current instance of ``Image``.
            Or (blc[0], blc[1], trc[0], trc[1],) or (center[0], center[1], r,
            None,) or (center[0], center[1], bmaj, e, bpa). Default ``None``.
        :param region2: (optional)
            Region to EXCLUDE in other instance of ``Image``. Or (blc[0],
            blc[1], trc[0], trc[1],) or (center[0], center[1], r, None,) or
            (center[0], center[1], bmaj, e, bpa). Default ``None``.
        :param upsample_factor: (optional)
            Upsampling factor. Images will be registered to within
            ``1 / upsample_factor`` of a pixel. For example
            ``upsample_factor == 20`` means the images will be registered
            within 1/20th of a pixel. If ``1`` then no upsampling.
            (default: ``100``)
        :param extended_output: (optioinal)
            Output all information from ``register_translation``? (default:
            ``False``)
        :param mask_cc: (optional)
            If some of images is instance of ``CleanImage`` class - should we
            mask clean components instead of image array? (default: ``False``)

        :return:
            Array of shifts (subpixeled) in each direction or full information
            from ``register_translation`` depending on ``extended_output``.
        """
        image1 = self.image.copy()
        if region1 is not None:
            mask1 = create_mask(self.image.shape, region1)
            if mask_cc and isinstance(self, CleanImage):
                raise NotImplementedError()
            image1[mask1] = 0.
        image2 = image.image.copy()
        if region2 is not None:
            mask2 = create_mask(image.image.shape, region2)
            if mask_cc and isinstance(image, CleanImage):
                raise NotImplementedError()
            image2[mask2] = 0.
        # Cross-correlate images
        shift, error, diffphase = register_translation(image1, image2,
                                                       upsample_factor)
        result = shift
        if extended_output:
            result = (shift, error, diffphase)
        return result

    # TODO: Implement physical sizes as vertexes of slice in ``Image``
    def slice(self, pix1, pix2):
        """
        Method that returns slice of image along line.

        :param pix1:
            Iterable of coordinates of first pixel.
        :param pix2:
            Iterable of coordinates of second pixel.
        :return:
            Numpy array of image values for given slice.
        """
        length = int(round(np.hypot(pix2[0] - pix1[0], pix2[1] - pix1[1])))
        if pix2[0] < pix1[0]:
            x = np.linspace(pix2[0], pix1[0], length)[::-1]
        else:
            x = np.linspace(pix1[0], pix2[0], length)
        if pix2[1] < pix1[1]:
            y = np.linspace(pix2[1], pix1[1], length)[::-1]
        else:
            y = np.linspace(pix1[1], pix2[1], length)

        return self.image[v_round(x).astype(np.int), v_round(y).astype(np.int)]


# TODO: Option for saving ``Image`` instance
# TODO: Default value of pixref - center of image.
class Image(BasicImage):
    """
    Class that represents images.
    """
    def __init__(self):
        super(Image, self).__init__()
        self.pixsize = None
        self.pixref = None
        self.pixrefval = None
        self.freq = None
        self.stokes = None

    def _construct(self, pixsize, pixref, stokes, freq, pixrefval, **kwargs):
        super(Image, self)._construct(**kwargs)
        self.pixsize = pixsize
        try:
            self.pixref = pixref
        except KeyError:
            self.pixref = (int(self.imsize / 2), int(self.imsize / 2))
        self.stokes = stokes
        self.freq = freq
        self.dy, self.dx = self.pixsize
        self.y_c, self.x_c = self.pixref
        try:
            self.pixrefval = pixrefval
        except KeyError:
            self.pixrefval = (0., 0.)
        self.x_c_val, self.y_c_val = self.pixrefval
        # Create coordinate arrays
        xsize, ysize = self.imsize
        x = np.linspace(0, xsize - 1, xsize)
        y = np.linspace(0, ysize - 1, ysize)
        xv, yv = np.meshgrid(x, y)
        x -= self.x_c
        xv -= self.x_c
        y -= self.y_c
        yv -= self.y_c
        x *= self.dx
        xv *= self.dx
        y *= self.dy
        yv *= self.dy
        self.x = x
        self.xv = xv
        self.y = y
        self.yv = yv

    def __eq__(self, other):
        """
        Compares current instance of ``Image`` class with other instance.
        """
        return (super(Image, self).__eq__(other) and
                self.pixsize == other.pixsize)

    def __ne__(self, other):
        """
        Compares current instance of ``Image`` class with other instance.
        """
        return super(Image, self).__ne__(other) or self.pixsize != other.pixsize

    @property
    def phys_size(self):
        """
        Shortcut for physical size of image.
        """
        return (self.imsize[0] * abs(self.pixsize[0]), self.imsize[1] *
                abs(self.pixsize[1]))

    # This method has no sense in ``BasicImage`` class as there are no physical
    # sizes here.
    def add_component(self, component):
        component.add_to_image(self)

    def add_model(self, model):
        if self.stokes != model.stokes:
            raise Exception
        model.add_to_image(self)

    def plot(self, blc=None, trc=None, clim=None, cmap=None, abs_levels=None,
             rel_levels=None, min_abs_level=None, min_rel_level=None, factor=2.,
             plot_color=False):
        """
        Plot image.

        :note:
            ``blc`` & ``trc`` are AIPS-like (from 1 to ``imsize``). Internally
            converted to python-like zero-indexing.

        """
        pass
        # plot(self.image, x=self.x, y=self.y, blc=blc, trc=trc, clim=clim,
        #      cmap=cmap, abs_levels=abs_levels, rel_levels=rel_levels,
        #      min_abs_level=min_abs_level, min_rel_level=min_rel_level,
        #      factor=factor, plot_color=plot_color)


# TODO: ``cc`` attribute should be collection of ``Model`` instances!
# TODO: Add method ``shift`` that shifts image (CCs and residulas). Is it better
# to shift in uv-domain?
class CleanImage(Image):
    """
    Class that represents image made using CLEAN algorithm.
    """
    def __init__(self):
        super(CleanImage, self).__init__()
        self._beam = CleanBeam()
        # FIXME: Make ``_residuals`` a 2D-array only. Don't need ``Image``
        # instance
        self._residuals = None
        self._image_original = None

    def _construct(self, **kwargs):
        """
        :param bmaj:
            Beam major axis [rad].
        :param bmin:
            Beam minor axis [rad].
        :param bpa:
            Beam positional angle [deg].
        :return:
        """
        super(CleanImage, self)._construct(**kwargs)
        # TODO: What if pixsize has different sizes???
        # FIXME: Beam has image twice the imsize. It's bad for plotting...
        kwargs["bmaj"] /= abs(kwargs["pixsize"][0])
        kwargs["bmin"] /= abs(kwargs["pixsize"][0])
        self._beam._construct(**kwargs)
        self._residuals = np.zeros(self.imsize, dtype=float)
        self._image_original = np.zeros(self.imsize, dtype=float)

    def from_hdulist(self, hdulist, ver=1):
        super(CleanImage, self).from_hdulist(hdulist)

        model = Model(stokes=self.stokes)
        model.from_hdulist(hdulist, ver=ver)
        self.add_model(model)

        self._residuals = self._image_original - self.cc_image

    def __eq__(self, other):
        """
        Compares current instance of ``Image`` class with other instance.
        """
        return (super(CleanImage, self).__eq__(other) and
                self._beam.__eq__(other._beam))

    def __ne__(self, other):
        """
        Compares current instance of ``Image`` class with other instance.
        """
        return (super(CleanImage, self).__ne__(other) or
                self._beam.__ne__(other._beam))

    @property
    def beam_image(self):
        """
        Shorthand for beam image.
        """
        return self._beam.image

    @property
    def beam(self):
        """
        Shorthand for beam parameters bmaj [mas], bmin [mas], bpa [deg].
        """
        return (self._beam.beam[0] * abs(self.pixsize[0]) / mas_to_rad,
                self._beam.beam[1] * abs(self.pixsize[0]) / mas_to_rad,
                self._beam.beam[2])

    @beam.setter
    def beam(self, beam_pars):
        """
        Set beam parameters.

        :param beam_pars:
            Iterable of bmaj [mas], bmin [mas], bpa [deg].
        """
        # FIXME: Here i create new instance. Should i implement setter for
        # beam parameters in ``CleanBeam``?
        self._beam = CleanBeam()
        self._beam._construct(bmaj=beam_pars[0]*mas_to_rad/abs(self.pixsize[0]),
                              bmin=beam_pars[1]*mas_to_rad/abs(self.pixsize[0]),
                              bpa=beam_pars[2], imsize=self.imsize)

    @property
    def image(self):
        """
        Shorthand for clean components convolved with original clean beam with
        residuals added (that is what ``Image.image`` contains).
        """
        return self._image_original

    @image.setter
    def image(self, image):
        if isinstance(image, Image):
            if self == image:
                self._image = image.image.copy()
            else:
                raise Exception("Images have incompatible parameters!")
        # If ``image`` is array-like
        else:
            image = np.atleast_2d(image).copy()
            if not self.imsize == np.shape(image):
                raise Exception("Images have incompatible parameters!")
            self._image = image

    @property
    def cc_image(self):
        """
        Shorthand for convolved clean components image.
        """
        return signal.fftconvolve(self._image, self.beam_image, mode='same')

    @property
    def cc(self):
        """
        Shorthand for image of clean components (didn't convolved with beam).
        """
        return self._image

    # FIXME: Should be read-only as residuals have sense only for naitive clean
    @property
    def residuals(self):
        return self._residuals

    def plot(self, to_plot, blc=None, trc=None, color_clim=None, cmap=None,
             abs_levels=None, rel_levels=None, min_abs_level=None,
             min_rel_level=None, factor=2., plot_color=False):
        """
        Plot image.

        :param to_plot:
            "cc", "ccr", "ccrr", "r" or "beam" - to plot only CC, CC Restored
            with beam, CC Restored with Residuals added, Residuals only or Beam.

        :note:
            ``blc`` & ``trc`` are AIPS-like (from 1 to ``imsize``). Internally
            converted to python-like zero-indexing.

        """
        plot_dict = {"cc": self._image, "ccr": self.image, "ccrr":
            self.image_w_residuals, "r": self._residuals.image,
                     "beam": self.beam}
        if plot_color:
            colors = plot_dict[to_plot]
            contours = None
        else:
            colors = None
            contours = plot_dict[to_plot]
        plot(contours, colors, x=self.x, y=self.y, blc=blc, trc=trc,
             color_clim=color_clim, cmap=cmap, abs_levels=abs_levels,
             rel_levels=rel_levels, min_abs_level=min_abs_level,
             min_rel_level=min_rel_level, k=factor)


#class MemImage(BasicImage, Model):
#    """
#    Class that represents image made using MEM algorithm.
#    """
#    pass

if __name__ == '__main__':
    image = CleanImage()
    import os
    image.from_fits(os.path.join('/home/ilya/data/3c273',
                                 '1226+023.u.2006_06_15.ict.fits'))


    # # Importing stuff
    # import os
    # from images import Images
    # from from_fits import create_clean_image_from_fits_file

    # abs_levels = [-0.0004] + [0.0004 * 2**j for j in range(15)]

    # data_dir = '/home/ilya/vlbi_errors/0952+179/2007_04_30/'
    # i_dir_c1 = data_dir + 'C1/im/I/'
    # q_dir_c1 = data_dir + 'C1/im/Q/'
    # u_dir_c1 = data_dir + 'C1/im/U/'
    # print "Creating PANG image..."
    # images = Images()
    # images.add_from_fits(fnames=[os.path.join(q_dir_c1, 'cc.fits'),
    #                              os.path.join(u_dir_c1, 'cc.fits')])
    # pang_image = images.create_pang_images()[0]

    # print "Creating PPOL image..."
    # images = Images()
    # images.add_from_fits(fnames=[os.path.join(q_dir_c1, 'cc.fits'),
    #                              os.path.join(u_dir_c1, 'cc.fits')])
    # ppol_image = images.create_pol_images()[0]

    # print "Creating I image..."
    # i_image = create_clean_image_from_fits_file(os.path.join(i_dir_c1,
    #                                                          'cc.fits'))
    # print "Creating FPOL image..."
    # images = Images()
    # images.add_from_fits(fnames=[os.path.join(i_dir_c1, 'cc.fits'),
    #                              os.path.join(q_dir_c1, 'cc.fits'),
    #                              os.path.join(u_dir_c1, 'cc.fits')])
    # fpol_image = images.create_fpol_images()[0]

    # # Creating masks
    # ppol_mask = np.zeros(ppol_image.imsize)
    # ppol_mask[ppol_image.image < 0.001] = 1

    # plot(contours=i_image.image_w_residuals, colors=fpol_image.image,
    #      vectors=pang_image.image, vectors_values=ppol_image.image,
    #      x=i_image.x[0, :], y=i_image.y[:, 0], blc=(240, 235), trc=(300, 370),
    #      colors_mask=ppol_mask, vectors_mask=ppol_mask, min_abs_level=0.0005)
    #      # plot_title="0952+179 C1",
    #      # outdir='/home/ilya/vlbi_errors/', outfile='0952+179_C1')
