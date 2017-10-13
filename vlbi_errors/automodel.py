import numpy as np
import os
import glob
import shutil
from scipy import ndimage
from uv_data import UVData
from model import Model
from cv_model import cv_difmap_models
from spydiff import (export_difmap_model, modelfit_difmap, import_difmap_model,
                     clean_difmap, append_component_to_difmap_model,
                     clean_n)
from components import CGComponent, EGComponent
from from_fits import (create_image_from_fits_file,
                       create_clean_image_from_fits_file,
                       create_model_from_fits_file)
from utils import mas_to_rad, infer_gaussian
from image import plot as iplot
from image import find_bbox
from image_ops import rms_image
from utils import create_mask
label_size = 16
import matplotlib
matplotlib.rcParams['xtick.labelsize'] = label_size
matplotlib.rcParams['ytick.labelsize'] = label_size
matplotlib.rcParams['axes.titlesize'] = 20
matplotlib.rcParams['axes.labelsize'] = label_size
matplotlib.rcParams['font.size'] = 20
matplotlib.rcParams['legend.fontsize'] = 20
import matplotlib.pyplot as plt
import tarfile


class FailedFindBestModelException(Exception):
    pass


def create_cc_model_uvf(uv_fits_path, mapsize_clean, path_to_script,
                        outname='image_cc_model.uvf', out_dir=None):
    """
    Function that creates uv-data set from CC-model.

    The rational is that FT of CC-model (that were derived using CLEAN-boxes) is
    free of off-source nosie.
    """
    if out_dir is None:
        out_dir = os.getcwd()
    uvdata = UVData(uv_fits_path)
    noise = uvdata.noise(use_V=True)
    # uv_fits_dir, uv_fits_fname = os.path.split(uv_fits_path)
    clean_n(uv_fits_path, 'cc.fits', 'I', mapsize_clean,
            path_to_script=path_to_script, niter=700,
            outpath=out_dir, clean_box=(1.5, -3, -2, 2.5),
            show_difmap_output=True)
    # ccimage = create_clean_image_from_fits_file(os.path.join(out_dir, 'cc.fits'))
    # rms = rms_image(ccimage)
    # blc, trc = find_bbox(ccimage.image, rms)
    # mask = create_mask(ccimage.image.shape, (blc[0], blc[1], trc[0], trc[1]))

    ccmodel = create_model_from_fits_file(os.path.join(out_dir, 'cc.fits'))
    # Here optionally filter CC

    uvdata.substitute([ccmodel])
    uvdata.noise_add(noise)
    uvdata.save(os.path.join(out_dir, outname))


def plot_clean_image_and_components(image, comps, outname=None):
    """
    :param image:
        Instance of ``CleanImage`` class.
    :param comps:
        Iterable of ``Components`` instances.
    :return:
        ``Figure`` object.
    """
    beam = image.beam
    rms = rms_image(image)
    blc, trc = find_bbox(image.image, rms, 10)
    # mask = create_mask(image.image.shape, (blc[0], blc[1], trc[0], trc[1]))
    fig = iplot(image.image, x=image.x, y=image.y, min_abs_level=3 * rms,
                beam=beam, show_beam=True, blc=blc, trc=trc, components=comps,
                close=True, colorbar_label="Jy/beam")
    if outname is not None:
        fig.savefig(outname, bbox_inches='tight', dpi=300)
    return fig


# TODO: Remove beam from ``bmaj``
def suggest_cg_component(uv_fits_path, mapsize_clean, path_to_script,
                         outname='image_cc.fits', out_dir=None):
    """
    Suggest single circular gaussian component using self-calibrated uv-data
    FITS file.
    :param uv_fits_path:
        Path to uv-data FITS-file.
    :param mapsize_clean:
        Iterable of image size (# pixels) and pixel size (mas).
    :param path_to_script:
        Path to difmap CLEANing script.
    :param outname: (optional)
        Name of file to save CC FITS-file. (default: ``image_cc.fits``)
    :param out_dir: (optional)
        Optional directory to save CC FITS-file. If ``None`` use CWD. (default:
        ``None``)
    :return:
        Instance of ``CGComponent``.
    """
    if out_dir is None:
        out_dir = os.getcwd()
    uv_fits_dir, uv_fits_fname = os.path.split(uv_fits_path)
    clean_difmap(uv_fits_fname, outname, 'I', mapsize_clean,
                 path=uv_fits_dir, path_to_script=path_to_script,
                 outpath=out_dir)

    image = create_clean_image_from_fits_file(os.path.join(out_dir, outname))
    beam = np.sqrt(image.beam[0] * image.beam[1])
    imsize = image.imsize[0]
    mas_in_pix = abs(image.pixsize[0] / mas_to_rad)
    amp, y, x, bmaj = infer_gaussian(image.image)
    x = mas_in_pix * (x - imsize / 2) * np.sign(image.dx)
    y = mas_in_pix * (y - imsize / 2) * np.sign(image.dy)
    bmaj *= mas_in_pix
    bmaj = np.sqrt(bmaj**2 - beam**2)
    return CGComponent(amp, x, y, bmaj), os.path.join(out_dir, outname)


def suggest_eg_component(uv_fits_path, mapsize_clean, path_to_script,
                         outname='image_cc.fits', out_dir=None):
    """
    Suggest single circular gaussian component using self-calibrated uv-data
    FITS file.
    :param uv_fits_path:
        Path to uv-data FITS-file.
    :param mapsize_clean:
        Iterable of image size (# pixels) and pixel size (mas).
    :param path_to_script:
        Path to difmap CLEANing script.
    :param outname: (optional)
        Name of file to save CC FITS-file. (default: ``image_cc.fits``)
    :param out_dir: (optional)
        Optional directory to save CC FITS-file. If ``None`` use CWD. (default:
        ``None``)
    :return:
        Instance of ``CGComponent``.
    """
    if out_dir is None:
        out_dir = os.getcwd()
    uv_fits_dir, uv_fits_fname = os.path.split(uv_fits_path)
    clean_difmap(uv_fits_fname, outname, 'I', mapsize_clean,
                 path=uv_fits_dir, path_to_script=path_to_script,
                 outpath=out_dir)

    image = create_clean_image_from_fits_file(os.path.join(out_dir, outname))
    beam = np.sqrt(image.beam[0] * image.beam[1])
    imsize = mapsize_clean[0]
    mas_in_pix = mapsize_clean[1]
    amp, y, x, bmaj = infer_gaussian(image.image)
    x = mas_in_pix * (x - imsize / 2) * np.sign(image.dx)
    y = mas_in_pix * (y - imsize / 2) * np.sign(image.dy)
    bmaj *= mas_in_pix
    bmaj = np.sqrt(bmaj ** 2 - beam ** 2)
    return EGComponent(amp, x, y, bmaj, 1.0, 0.0), os.path.join(out_dir, outname)


def create_residuals(uv_fits_path, model=None, out_fname='residuals.uvf',
                     out_dir=None):
    if model is None:
        return uv_fits_path
    if out_dir is None:
        out_dir = os.getcwd()
    out_fits_path = os.path.join(out_dir, out_fname)
    uvdata = UVData(uv_fits_path)
    uvdata_ = UVData(uv_fits_path)
    uvdata_.substitute([model])
    uvdata_residual = uvdata - uvdata_
    uvdata_residual.save(out_fits_path, rewrite=True)
    return out_fits_path


def find_best(files, delta_flux=0.001, delta_size=0.001, small_size=10**(-5)):
    """
    Select best model from given difmap model files.

    :param files:
        Iterable of paths difmap models.
    :return:
        Path to difmap model file with best model.
    """
    out_dir = os.path.split(files[0])[0]
    files = [os.path.split(file_path)[-1] for file_path in files]
    files = sorted(files, key=lambda x: int(x.split('_')[-1].split('.')[0]))
    files = [os.path.join(out_dir, file_) for file_ in files]
    comps = list()
    for file_ in files:
        comps_ = import_difmap_model(file_)
        comps.append(comps_[0])

    fluxes = np.array([comp.p[0] for comp in comps])
    fluxes_inv = fluxes[::-1]
    a = (abs(fluxes_inv - fluxes_inv[0]) < delta_flux)[::-1]
    try:
        n_flux = list(ndimage.binary_opening(a, structure=np.ones(2)).astype(np.int)).index(1)
    except IndexError:
        n_flux = 0

    sizes = np.array([comp.p[3] for comp in comps])
    sizes_inv = sizes[::-1]
    a = (abs(sizes_inv - sizes_inv[0]) < delta_size)[::-1]
    try:
        n_size = list(ndimage.binary_opening(a, structure=np.ones(2)).astype(np.int)).index(1)
    except IndexError:
        n_size = 0

    # Now go from largest model to simpler ones and excluding models with small
    # components
    n = max(n_flux, n_size)
    print("Flux+Size==>{}".format(n))
    if n == 1:
        raise FailedFindBestModelException
    n_best = n
    for model_file in files[:n][::-1]:
        comps = import_difmap_model(model_file)
        small_sizes = [comp.p[3] > small_size for comp in comps[1:]]
        if not np.alltrue(small_sizes):
            n_best = n_best - 1

    return files[n_best-1]


def stop_adding_models(files, n_check=5, delta_flux_min=0.001,
                       delta_size_min=0.001):
    """
    Since last ``n_check`` models parameters of core haven't changed.
    """
    out_dir = os.path.split(files[0])[0]
    files = [os.path.split(file_path)[-1] for file_path in files]
    files = sorted(files, key=lambda x: int(x.split('_')[-1].split('.')[0]))
    files = [os.path.join(out_dir, file_) for file_ in files]
    last_file = files[-1]
    files = files[-n_check-1: -1]
    comps = list()
    last_comp = import_difmap_model(last_file)[0]
    for file_ in files:
        comps_ = import_difmap_model(file_)
        comps.append(comps_[0])
    last_flux = last_comp.p[0]
    last_size = last_comp.p[3]
    fluxes = np.array([comp.p[0] for comp in comps])
    sizes = np.array([comp.p[3] for comp in comps])
    delta_fluxes = abs(fluxes - last_flux)
    delta_sizes = abs(sizes - last_size)
    return np.alltrue(delta_fluxes < delta_flux_min) or np.alltrue(delta_sizes < delta_size_min)


def stop_adding_models_(files, n_check=5, delta_flux_min=0.001,
                        delta_size_min=0.001):
    """
    Each of the last ``n_check`` models differs from previous one by less then
    specified values.
    """
    out_dir = os.path.split(files[0])[0]
    files = [os.path.split(file_path)[-1] for file_path in files]
    files = sorted(files, key=lambda x: int(x.split('_')[-1].split('.')[0]))
    files = [os.path.join(out_dir, file_) for file_ in files]
    files = files[-n_check-1:]
    comps = list()
    for file_ in files:
        comps_ = import_difmap_model(file_)
        comps.append(comps_[0])
    fluxes = np.array([comp.p[0] for comp in comps])
    sizes = np.array([comp.p[3] for comp in comps])
    delta_fluxes = abs(fluxes[:-1]-fluxes[1:])
    delta_sizes = abs(sizes[:-1]-sizes[1:])
    return np.alltrue(delta_fluxes < delta_flux_min) and np.alltrue(delta_sizes < delta_size_min)


def automodel_uv_fits(uv_fits_path, out_dir, mapsize_clean=None,
                      path_to_script='/home/ilya/github/vlbi_errors/difmap/final_clean_nw',
                      core_elliptic=False, compute_CV=False, n_max_comps=30,
                      n_check=5):
    # mapsize_clean = (1024, 0.1)
    # out_dir = '/home/ilya/github/vlbi_errors/0552'
    # uv_fits_fname = '0552+398.u.2006_07_07.uvf'
    # uv_fits_path = os.path.join(out_dir, uv_fits_fname)
    # path_to_script = '/home/ilya/github/vlbi_errors/difmap/final_clean_nw'
    uv_fits_dir, uv_fits_fname = os.path.split(uv_fits_path)
    source = uv_fits_fname.split(".")[0]
    freq = uv_fits_fname.split(".")[1]

    if mapsize_clean is None:
        if freq == 'u':
            mapsize_clean = (1024, 0.1)
        elif freq == 'q':
            mapsize_clean = (1024, 0.03)
        else:
            raise Exception("Indicate mapsize_clean!")

    epoch = uv_fits_fname.split(".")[2]
    uvdata = UVData(uv_fits_path)
    freq_hz = uvdata.frequency
    model = None
    cv_scores = list()
    ccimage_orig = None

    # # First create cc-model and transfer it to uv-plane
    # print("Creating UV-data with CLEAN-model instead of real data")
    # create_cc_model_uvf(uv_fits_path, (1024, 0.1), path_to_script=path_to_script,
    #                     out_dir=out_dir)
    # # Use this for model selection
    # uv_fits_path = os.path.join(out_dir, 'image_cc_model.uvf')

    for i in range(1, n_max_comps+1):
        print("{}-th iteration begins".format(i))
        uv_fits_path_res = create_residuals(uv_fits_path, model=model,
                                            out_dir=out_dir)
        # 1. Modelfit in difmap with CG
        print("Suggesting CG component to add...")
        if i == 1 and core_elliptic:
            cg, image_cc_fits = suggest_eg_component(uv_fits_path_res, mapsize_clean,
                                                     path_to_script, out_dir=out_dir)
        else:
            cg, image_cc_fits = suggest_cg_component(uv_fits_path_res, mapsize_clean,
                                                     path_to_script, out_dir=out_dir)
        # Saving original CLEAN image
        shutil.copy(image_cc_fits, os.path.join(out_dir, 'image_cc_orig.fits'))
        if ccimage_orig is None:
            ccimage_orig = create_clean_image_from_fits_file(image_cc_fits)
            sign_x = np.sign(ccimage_orig.dx)
            sign_y = np.sign(ccimage_orig.dy)
        print("Suggested: {}".format(cg.p))

        if i > 1:
            # If this is not first iteration then append component to existing file
            print("Our initial model will be last one + new component.")
            shutil.copy(os.path.join(out_dir, '{}_{}_{}_fitted_{}.mdl'.format(source, freq, epoch, i-1)),
                        os.path.join(out_dir, 'init_{}.mdl'.format(i)))
            print("Appending component to model")
            append_component_to_difmap_model(cg, os.path.join(out_dir, 'init_{}.mdl'.format(i)),
                                             freq_hz)
        else:
            # If this is first iteration then create model file
            print("Initialize model")
            export_difmap_model([cg],
                                os.path.join(out_dir, 'init_{}.mdl'.format(i)),
                                freq_hz)

        modelfit_difmap(uv_fits_fname, 'init_{}.mdl'.format(i),
                        '{}_{}_{}_fitted_{}.mdl'.format(source, freq, epoch, i), path=uv_fits_dir,
                        mdl_path=out_dir, out_path=out_dir, niter=100)
        model = Model(stokes='I')
        comps = import_difmap_model('{}_{}_{}_fitted_{}.mdl'.format(source, freq, epoch, i), out_dir)
        plot_clean_image_and_components(ccimage_orig, comps,
                                        outname=os.path.join(out_dir, "{}_{}_{}_image_{}.png".format(source, freq, epoch, i)))
        model.add_components(*comps)

        # Cross-Validation
        if compute_CV:
            cv_score = cv_difmap_models([os.path.join(out_dir,
                                                      '{}_{}_{}_fitted_{}.mdl'.format(source, freq, epoch, i))],
                                         uv_fits_path, K=5, out_dir=out_dir, n_rep=1)
            cv_scores.append((cv_score[0][0][0], cv_score[1][0][0]))

        # Check if we need go further
        if i > n_check:
            fitted_model_files = glob.glob(os.path.join(out_dir, "{}_{}_{}_fitted*".format(source, freq, epoch)))
            if stop_adding_models(fitted_model_files, n_check=n_check):
                break

    # # Optionally plot CV-scores
    # import matplotlib.pyplot as plt
    # plt.errorbar(range(1, len(cv_scores)+1), np.atleast_2d(cv_scores)[:, 0],
    #              yerr=np.atleast_2d(cv_scores)[:, 1], fmt='.k')
    # plt.plot(range(1, len(cv_scores)+1), np.atleast_2d(cv_scores)[:, 0])
    # plt.show()

    # Choose best model
    files = glob.glob(os.path.join(out_dir, "{}_{}_{}_fitted*".format(source, freq, epoch)))
    # Save files in archive
    with tarfile.open(os.path.join(out_dir, "{}_fitted_models.tar.gz".format(source)), "w:gz") as tar:
        for fn in files:
            tar.add(fn, arcname=os.path.split(fn)[-1])

    files = [os.path.split(file_path)[-1] for file_path in files]
    files = sorted(files, key=lambda x: int(x.split('_')[-1].split('.')[0]))
    files = [os.path.join(out_dir, file_) for file_ in files]
    comps = list()
    for file_ in files:
        comps_ = import_difmap_model(file_)
        comps.append(comps_[0])

    try:
        best_model_file = find_best(files)
        k = files.index(best_model_file) + 1
    except FailedFindBestModelException:
        return None

    fig, axes = plt.subplots(2, 1, sharex=True)
    axes[0].plot(range(1, len(comps)+1), [comp.p[0] for comp in comps])
    axes[0].plot(range(1, len(comps)+1), [comp.p[0] for comp in comps], '.k')
    axes[0].set_ylabel("Core Flux, [Jy]")
    axes[1].plot(range(1, len(comps)+1), [comp.p[3] for comp in comps])
    axes[1].plot(range(1, len(comps)+1), [comp.p[3] for comp in comps], '.k')
    axes[1].set_xlabel("Number of components")
    axes[1].set_ylabel("Core Size, [mas]")
    axes[0].axvline(k)
    axes[1].axvline(k)
    fig.savefig(os.path.join(out_dir, '{}_{}_{}_core_parameters_vs_ncomps.png'.format(source, freq, epoch)),
                bbox_inches='tight', dpi=200)

    # Clean
    files = glob.glob(
        os.path.join(out_dir, "{}_{}_{}_fitted*".format(source, freq, epoch)))
    for fn in files:
        os.unlink(fn)

    return best_model_file
