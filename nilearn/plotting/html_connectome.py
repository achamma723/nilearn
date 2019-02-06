import functools
import json
import warnings

import numpy as np
from scipy import sparse
from .. import datasets
from . import cm

from .js_plotting_utils import (add_js_lib, HTMLDocument, mesh_to_plotly,
                                encode, colorscale, get_html_template,
                                to_color_strings)


class ConnectomeView(HTMLDocument):
    pass


def _prepare_line(edges, nodes):
    path_edges = np.zeros(len(edges) * 3, dtype=int)
    path_edges[::3] = edges
    path_edges[1::3] = edges
    path_nodes = np.zeros(len(nodes) * 3, dtype=int)
    path_nodes[::3] = nodes[:, 0]
    path_nodes[1::3] = nodes[:, 1]
    return path_edges, path_nodes


def _get_connectome(adjacency_matrix, coords, threshold=None,
                    cmap=cm.cold_hot, symmetric_cmap=True):
    connectome = {}
    coords = np.asarray(coords, dtype='<f4')
    adjacency_matrix = adjacency_matrix.copy()
    colors = colorscale(
        cmap, adjacency_matrix.ravel(), threshold=threshold,
        symmetric_cmap=symmetric_cmap)
    connectome['colorscale'] = colors['colors']
    connectome['cmin'] = float(colors['vmin'])
    connectome['cmax'] = float(colors['vmax'])
    if threshold is not None:
        adjacency_matrix[
            np.abs(adjacency_matrix) <= colors['abs_threshold']] = 0
    s = sparse.coo_matrix(adjacency_matrix)
    nodes = np.asarray([s.row, s.col], dtype=int).T
    edges = np.arange(len(nodes))
    path_edges, path_nodes = _prepare_line(edges, nodes)
    connectome["_con_w"] = encode(np.asarray(s.data, dtype='<f4')[path_edges])
    c = coords[path_nodes]
    x, y, z = c.T
    for coord, cname in [(x, "x"), (y, "y"), (z, "z")]:
        connectome["_con_{}".format(cname)] = encode(
            np.asarray(coord, dtype='<f4'))
    connectome["markers_only"] = False
    return connectome


def _get_markers(coords, colors):
    connectome = {}
    coords = np.asarray(coords, dtype='<f4')
    x, y, z = coords.T
    for coord, cname in [(x, "x"), (y, "y"), (z, "z")]:
        connectome["_con_{}".format(cname)] = encode(
            np.asarray(coord, dtype='<f4'))
    connectome["marker_color"] = to_color_strings(colors)
    connectome["markers_only"] = True
    return connectome


def _make_connectome_html(connectome_info, embed_js=True):
    plot_info = {"connectome": connectome_info}
    mesh = datasets.fetch_surf_fsaverage()
    for hemi in ['pial_left', 'pial_right']:
        plot_info[hemi] = mesh_to_plotly(mesh[hemi])
    as_json = json.dumps(plot_info)
    as_html = get_html_template(
        'connectome_plot_template.html').safe_substitute(
            {'INSERT_CONNECTOME_JSON_HERE': as_json})
    as_html = add_js_lib(as_html, embed_js=embed_js)
    return ConnectomeView(as_html)


def _deprecate_params_view_connectome(func):
    """ Decorator to deprecate spcific parameters in view_connectome()
     without modifying view_connectome().
     """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        _warn_deprecated_params_view_connectome(kwargs)
        kwargs = _transfer_deprecated_param_vals_view_connectome(kwargs)
        return func(*args, **kwargs)
    
    return wrapper


@_deprecate_params_view_connectome
def view_connectome(adjacency_matrix, node_coords, edge_threshold=None,
                    edge_cmap=cm.cyan_orange, symmetric_cmap=True,
                    linewidth=6., node_size=3.,
                    **kwargs):
    """
    Insert a 3d plot of a connectome into an HTML page.

    Parameters
    ----------
    adjacency_matrix : ndarray, shape=(n_nodes, n_nodes)
        the weights of the edges.

    node_coords : ndarray, shape=(n_nodes, 3)
        the coordinates of the nodes in MNI space.

    edge_threshold : str, number or None, optional (default=None)
        If None, no thresholding.
        If it is a number only connections of amplitude greater
        than threshold will be shown.
        If it is a string it must finish with a percent sign,
        e.g. "25.3%", and only connections of amplitude above the
        given percentile will be shown.

    edge_cmap : str or matplotlib colormap, optional

    symmetric_cmap : bool, optional (default=True)
        Make colormap symmetric (ranging from -vmax to vmax).

    linewidth : float, optional (default=6.)
        Width of the lines that show connections.

    node_size : float, optional (default=3.)
        Size of the markers showing the seeds.

    Returns
    -------
    ConnectomeView : plot of the connectome.
        It can be saved as an html page or rendered (transparently) by the
        Jupyter notebook. Useful methods are :

        - 'resize' to resize the plot displayed in a Jupyter notebook
        - 'save_as_html' to save the plot to a file
        - 'open_in_browser' to save the plot and open it in a web browser.

    See Also
    --------
    nilearn.plotting.plot_connectome:
        projected views of a connectome in a glass brain.

    nilearn.plotting.view_markers:
        interactive plot of colored markers

    nilearn.plotting.view_surf, nilearn.plotting.view_img_on_surf:
        interactive view of statistical maps or surface atlases on the cortical
        surface.

    """
    connectome_info = _get_connectome(
        adjacency_matrix, node_coords, threshold=edge_threshold, cmap=edge_cmap,
        symmetric_cmap=symmetric_cmap)
    connectome_info["line_width"] = linewidth
    connectome_info["marker_size"] = node_size
    return _make_connectome_html(connectome_info)


def _warn_deprecated_params_view_connectome(kwargs):
    """ For view_connectome(), raises warnings about deprecated parameters.
    """
    all_deprecated_params = {'coords': 'node_coords',
                             'threshold': 'edge_threshold',
                             'cmap': 'edge_cmap',
                             'marker_size': 'node_size',
                             }
    used_deprecated_params = set(kwargs.keys()
                                 ).intersection(all_deprecated_params.keys())
    for deprecated_param_ in used_deprecated_params:
        replacement_param = all_deprecated_params[deprecated_param_]
        param_deprecation_msg = (
            'The parameter "{}" will be removed in a future version of Nilearn.'
            'Please use the parameter "{}" instead.'.format(deprecated_param_,
                                                            replacement_param,
                                                            )
        )
        warnings.filterwarnings('always', message=param_deprecation_msg)
        warnings.warn(category=DeprecationWarning,
                  message=param_deprecation_msg,
                  stacklevel=3)


def _transfer_deprecated_param_vals_view_connectome(kwargs):
    """ For view_connectome(), reassigns new parameters the values passed
    to their corresponding deprecated parameters.
    """
    coords = kwargs.setdefault('coords', None)
    threshold = kwargs.setdefault('threshold', None)
    cmap = kwargs.setdefault('cmap', None)
    marker_size = kwargs.setdefault('marker_size', None)
    
    if coords is not None:
        kwargs['node_coords'] = coords
    if threshold:
        kwargs['edge_threshold'] = threshold
    if cmap:
        kwargs['edge_cmap'] = cmap
    if marker_size:
        kwargs['node_size'] = marker_size
    return kwargs


def view_markers(coords, colors=None, marker_size=5.):
    """
    Insert a 3d plot of markers in a brain into an HTML page.

    Parameters
    ----------
    coords : ndarray, shape=(n_nodes, 3)
        the coordinates of the nodes in MNI space.

    colors : ndarray, shape=(n_nodes,)
        colors of the markers: list of strings, hex rgb or rgba strings, rgb
        triplets, or rgba triplets (i.e. formats accepted by matplotlib, see
        https://matplotlib.org/users/colors.html#specifying-colors)

    marker_size : float, optional (default=3.)
        Size of the markers showing the seeds.

    Returns
    -------
    ConnectomeView : plot of the markers.
        It can be saved as an html page or rendered (transparently) by the
        Jupyter notebook. Useful methods are :

        - 'resize' to resize the plot displayed in a Jupyter notebook
        - 'save_as_html' to save the plot to a file
        - 'open_in_browser' to save the plot and open it in a web browser.

    See Also
    --------
    nilearn.plotting.plot_connectome:
        projected views of a connectome in a glass brain.

    nilearn.plotting.view_connectome:
        interactive plot of a connectome.

    nilearn.plotting.view_surf, nilearn.plotting.view_img_on_surf:
        interactive view of statistical maps or surface atlases on the cortical
        surface.

    """
    if colors is None:
        colors = ['black' for i in range(len(coords))]
    connectome_info = _get_markers(coords, colors)
    connectome_info["marker_size"] = marker_size
    return _make_connectome_html(connectome_info)
