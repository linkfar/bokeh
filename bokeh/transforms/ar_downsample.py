from __future__ import print_function
from ..plotting import image_rgba, image, multi_line, curdoc
from ..plot_object import PlotObject
from ..objects import ServerDataSource,  Glyph, Range1d, Color
from ..properties import (Instance, Any, Either,
                          Int, Float, List, Bool, String)
import bokeh.colors as colors
import numpy as np
import math

import logging
logger = logging.getLogger(__file__)

_AR_MESSAGE = """
---------------------------------------------------
Error loading the abstract_rendering package.

To use the ar_downsample module, you must install the
abstract rendering framework.
This can be installed with conda, pip or by
cloning from https://github.com/ContinuumIO/abstract_rendering
Questions and feedback can be directed to
Joseph Cottam (jcottam@indiana.edu)
-------------------------------------------------------
"""


def _loadAR():
    """
    Utility to load abstract rendering (AR).  Keeps the import from occurring
    unless you actually try to use AR.  MUST be called before actually
    calling any AR package items (typically only invoked on the server
    in response to an AR-reliant plot request).

    This is more complex than just an import because
    AR is exposed as several backbone modules.  If the AR modules
    were directly imported, then errors would occur whenever ar_downsample
    is imported.  This causes error messages on python client side (where
    AR isn't actually needed) and on the server side even when AR isn't used.
    Since the AR modules are used throughout this module, just importing at
    use point inside this module is cumbersome.  Using 'globals()' and
    importlib allows this method to be called before any AR proper items
    are used but still have the imports appear at the module level.
    """
    try:
        from importlib import import_module
        globals()["ar"] = import_module("abstract_rendering.core")
        globals()["categories"] = import_module("abstract_rendering.categories")
        globals()["contour"] = import_module("abstract_rendering.contour")
        globals()["infos"] = import_module("abstract_rendering.infos")
        globals()["general"] = import_module("abstract_rendering.general")
        globals()["glyphset"] = import_module("abstract_rendering.glyphset")
        globals()["npg"] = import_module("abstract_rendering.numpyglyphs")
        globals()["numeric"] = import_module("abstract_rendering.numeric")
        globals()["util"] = import_module("abstract_rendering.util")
    except:
        print(_AR_MESSAGE)
        raise


class Proxy(PlotObject):
    """
    Proxy objects stand in for the abstract rendering (AR) configuration
    classes. Basically, the AR implementation doesn't rely on Bokeh, so
    it doesn't know about the properties BUT the Bokeh needs be able to
    construct/modify/inspect AR configurations.  Proxy classes hold the
    relevant parameters for constructing AR classes in a way that Bokeh
    can inspect. Furthermore, 'reify' produces an AR class from a
    proxy instance.
    """
    def reify(self, **kwargs):
        raise NotImplementedError("Unimplemented")


# ------ Aggregators -------------
class Sum(Proxy):
    "Add up all incoming values"
    def reify(self, **kwargs):
        return numeric.Sum()


class Count(Proxy):
    "Count how many items there are (ignores values)"
    def reify(self, **kwargs):
        glyphs = kwargs.get('glyphset', None)
        if isinstance(glyphs, npg.Glyphset):
            return npg.PointCount()
        else:
            return numeric.Count()


class CountCategories(Proxy):
    "Count how many items there are in provided categories"
    def reify(self, **kwargs):
        glyphs = kwargs.get('glyphset', None)
        if isinstance(glyphs, npg.Glyphset):
            return npg.PointCountCategories()
        else:
            return categories.CountCategories()


# ------ Infos ---------
class Const(Proxy):
    "Return a single value"
    val = Any()

    def reify(self, **kwargs):
        return infos.const(self.val)


class Encode(Proxy):
    "Convert a set of values to numeric codes."
    cats = List(Any)
    defcat = Int(-1)

    def reify(self, **kwargs):
        return infos.encode(self.cats, defcat=self.defcat)


class AutoEncode(Proxy):
    "Convert a set of values to numeric codes."

    def reify(self, **kwargs):
        return infos.AutoEncode()


# ----- Shaders ---------
# Out types to support:
#   image -- grid of values
#   rgb_image -- grid of colors
#   poly_line -- multi-segment lines

class Shader(Proxy):
    def __add__(self, other):
        "Build a sequence of shaders"
        return Seq(first=self, second=other)

    def reformat(self, result, *args):
        """
        Modify the standard AR shader output to one that Bokeh can use.
        Response to 'None' should produce an empty basic dataset.

        The default behavior for None is [[0]] (most shaders produce images).
        The default behavior for all other values is identity.
        """
        return np.array([[0]]) if result is None else result


class Seq(Shader):
    "Sequence of shaders"
    first = Instance(Shader)
    second = Instance(Shader)

    def reify(self, **kwargs):
        return self.first.reify(**kwargs) + self.second.reify(**kwargs)

    def __getattr__(self, name):
        if name == 'out':
            self.out = self.second.out
            return self.out
        else:
            raise AttributeError(name)

    def reformat(self, result, *args):
        return self.second.reformat(result, *args)


class Id(Shader):
    "Identity shader.  A safe default."
    out = "image"

    def reify(self, **kwargs):
        return general.Id()


class BinarySegment(Shader):
    """
    Divide the input space into two regions.

    divider - Value that divides the two regions
    high - Value for regions equal to or above the divider
    low - Value for cells below divider
    """
    out = "image"
    high = Any
    low = Any
    divider = Any   # TODO: Restrict to numbers...

    def reify(self, **kwargs):
        return numeric.BinarySegment(self.low, self.high, self.divider)


class Interpolate(Shader):
    "Interpolate between high and low number"
    out = "image"
    high = Any     # TODO: Restrict to numbers...
    low = Any

    def reify(self, **kwargs):
        return numeric.Interpolate(self.low, self.high)


class ImageShader(Shader):
    out = "image_rgb"

    def _reformatColor(self, color):
        if isinstance(color, tuple) or isinstance(color, list):
            parts = len(color)
            if parts == 3:
                return tuple(color)+(255,)
            if parts == 4:
                return tuple(color[0:3]) + (min(abs(color[3])*255, 255),)
            raise ValueError("Improperly formatted tuple for color %s" % color)

        if isinstance(color, str) or isinstance(color, unicode):
            if color[0] == "#":
                color = color.lstrip('#')
                lv = len(color)
                rgb = tuple(int(color[i:i + lv // 3], 16) for i in range(0, lv, lv // 3))
                return [rgb[0], rgb[1], rgb[2], 255]
            else:
                try:
                    rgb = getattr(colors, color).to_rgb()
                    return [rgb.r, rgb.g, rgb.b, 255]
                except:
                    raise ValueError("Unknown color string %s" % color)

    def reformat(self, image, *args):
        if image is None:
            return np.array([[0]])
        else:
            if not image.flags.contiguous:
                # TODO: Numpyglyphs *sometimes* return a non-continugous array?
                image = np.ascontiguousarray(image)
            return image.view(dtype=np.int32).reshape(image.shape[0:2])


class ToCounts(Shader):
    "Convert count-of-categories to just counts"
    out = "image"

    def reify(self, **kwargs):
        return categories.ToCounts()


class NonZeros(Shader):
    "How many non-zero categories are there?"
    out = "image"

    def reify(self, **kwargs):
        return categories.NonZeros()


class Ratio(Shader):
    "Ratio of some category to total of all categories."
    out = "image"
    focus = Int(-1)

    def reify(self, **kwargs):
        return categories.Ratio(focus=self.focus)


class HDAlpha(ImageShader):
    colors = List(Color)
    background = Color((255, 255, 255, 0))
    alphamin = Float(.3)
    log = Bool(False)
    base = Int(10)

    def reify(self, **kwargs):
        colors = map(self._reformatColor, self.colors)
        return categories.HDAlpha(
                colors,
                background=self._reformatColor(self.background),
                alphamin=self.alphamin,
                log=self.log,
                logbase=self.base)


class InterpolateColor(ImageShader):
    """
    Interpolate between a high and low color

    * high - High color (default: red)
    * low - Low color (default: white)
    * reserve - Color for empty values (default: transparent)
    * empty - Empty value (default: 0)

    """
    # TODO: Make color format conversion fluid
    #       ...possibly by some change to properties.Color
    out = "image_rgb"
    high = Color((255, 0, 0, 1))
    low = Color((255, 255, 255, 1))
    reserve = Color((255, 255, 255, 0))
    empty = Any(0)

    def reify(self, **kwargs):
        return numeric.InterpolateColors(
            self._reformatColor(self.low),
            self._reformatColor(self.high),
            reserve=self._reformatColor(self.reserve),
            empty=self.empty)


class Sqrt(Shader):
    "Square root of all values"
    out = "image"

    def reify(self, **kwargs):
        return numeric.Sqrt()


class Cuberoot(Shader):
    "Cube root of all values"
    out = "image"

    def reify(self, **kwargs):
        return numeric.Cuberoot()


class Log(Shader):
    "Log (base 10) of values"
    out = "image"

    def reify(self, **kwargs):
        return npg.Log10()


class Spread(Shader):
    """Spread values out in a regular pattern from their origin."""
    # TODO: Add shape parameter

    out = "image"
    factor = Int
    shape = String("circle")
    anti_alias = Bool(False)

    def reify(self, **kwargs):
        return npg.Spread(factor=self.factor,
                          shape=self.shape,
                          anti_alias=self.anti_alias)


class Contour(Shader):
    """
    ISO Contours

    levels -- Either how many ISO contours to make (int)
              or the exact contour levels (list).
              Both cases indicate how many contour lines to create.
    """
    out = "poly_line"
    levels = Either(Int, List(Float), default=5)

    def reify(self, **kwargs):
        return contour.Contour(levels=self.levels, points=False)

    def reformat(self, contours, *args):
        if contours is None:
            return {'xxs': [], 'yys': [], 'levels': []}

        xxs = []
        yys = []
        levels = sorted(contours.keys())
        (xmin, ymin) = args

        # Re-arrange results and project xs/ys back to the data space
        for level in levels:
            (xs, ys) = contours[level]
            xs = xs+(xmin-1)  # HACK: Why is this -1 required?
            ys = ys+(ymin-1)  # HACK: Why is this -1 required?
            xxs.append(xs)
            yys.append(ys)

        return {'levels': levels,
                'xs': xxs,
                'ys': yys}


# ------------------  Control Functions ----------------
def replot(plot, agg=Count(), info=Const(val=1), shader=Id(),
           remove_original=True, palette=["Spectral-11"], points=False,
           **kwargs):
    """
    Treat the passed plot as an base plot for abstract rendering, generate the
    proper Bokeh plot based on the passed parameters.

    This is a convenience for:
    > src=source(plot, ...)
    > <plot-type>(source=src, <params>, **ar.mapping(src))

    Transfers plot title, width, height from the original plot

    **kwargs -- Arguments for the source function EXCEPT reserve_val
                and reserve_color (if present)
    returns -- A new plot
    """

    # Transfer relevant named arguments
    props = dict()
    props['plot_width'] = kwargs.pop('plot_width', plot.plot_width)
    props['plot_height'] = kwargs.pop('plot_height', plot.plot_height)
    props['title'] = kwargs.pop('title', plot.title)

    # TODO: Find a list somewhere for plot-type-specific options and transfer out using that list.
    #       Otherwise, this section will be horribly unmanageable.
    options = ['reserve_val', 'reserve_color', 'line_color', 'tools']
    for opt in options:
        if opt in kwargs:
            props[opt] = kwargs.pop(opt)

    src = source(plot, agg, info, shader,
                 remove_original, palette, points, **kwargs)
    props.update(mapping(src))

    if shader.out == "image":
        return image(source=src, **props)
    elif shader.out == "image_rgb":
        return image_rgba(source=src, **props)
    elif shader.out == "poly_line":
        return multi_line(source=src, **props)
    else:
        raise ValueError("Unhandled output type %s" % shader.out)


# TODO: Move reserve control up here or palette control down.  Probably related to refactoring palette into a model-backed type
def source(plot, agg=Count(), info=Const(val=1), shader=Id(),
           remove_original=True, palette=["Spectral-11"],
           points=False, balancedZoom=False, **kwargs):
    # Acquire information from renderer...
    # TODO: How to be more specific about what to do AR on?
    #       Currently just takes the first renderer with a server data source
    rend = [r for r in plot.renderers
            if (isinstance(r, Glyph)
                and hasattr(r, "server_data_source")
                and r.server_data_source is not None)][0]
    datasource = rend.server_data_source
    kwargs['data_url'] = datasource.data_url
    kwargs['owner_username'] = datasource.owner_username

    spec = rend.vm_serialize()['glyphspec']

    # TODO: Use reformat here?

    if shader.out == "image" or shader.out == "image_rgb":
        kwargs['data'] = {'image': [],
                          'x': [0],
                          'y': [0],
                          'global_x_range': [0, 50],
                          'global_y_range': [0, 50],
                          'global_offset_x': [0],
                          'global_offset_y': [0],
                          'dw': [1],
                          'dh': [1],
                          'palette': palette,
                          'render_state': {}}
    elif shader.out == "poly_line":
        kwargs['data'] = {'xs': [[]],
                          'ys': [[]],
                          'render_state': {}}
    else:
        raise ValueError("Unrecognized shader output type %s" % shader.out)

    # Remove the base plot (if requested)
    if remove_original and plot in curdoc().context.children:
        curdoc().context.children.remove(plot)

    kwargs['transform'] = {
        'resample': "abstract rendering",
        'agg': agg,
        'info': info,
        'shader': shader,
        'glyphspec': spec,
        'balancedZoom': balancedZoom,
        'points': points}
    return ServerDataSource(**kwargs)


def mapping(source):
    "Setup property mapping dictionary from source to output glyph type."

    trans = source.transform
    out = trans['shader'].out

    if out == 'image' or out == 'image_rgb':
        keys = source.data.keys()
        m = dict(zip(keys, keys))
        m['x_range'] = Range1d(start=0, end=0)
        m['y_range'] = Range1d(start=0, end=0)
        return m
    elif out == 'poly_line':
        keys = source.data.keys()
        m = dict(zip(keys, keys))
        return m

    else:
        raise ValueError("Unrecognized shader output type %s" % out)


def make_glyphset(xcol, ycol, datacol, glyphspec, transform):
    # TODO: Do more detection to find if it is an area implantation.
    #       If so, make a selector with the right shape pattern and use a point shaper
    shaper = _shaper(glyphspec, transform['points'])
    if isinstance(shaper, glyphset.ToPoint):
        points = np.zeros((len(xcol), 4), order="F")
        points[:, 0] = xcol
        points[:, 1] = ycol
        glyphs = npg.Glyphset(points, datacol)
    else:
        glyphs = glyphset.Glyphset([xcol, ycol], datacol,
                                   shaper, colMajor=True)
    return glyphs


def _generate_render_state(plot_state):
    data_x_span = float(_span(plot_state['data_x']))
    data_y_span = float(_span(plot_state['data_y']))

    data_x_span = math.ceil(data_x_span * 100) / 100.0
    data_y_span = math.ceil(data_y_span * 100) / 100.0

    return {'x_span': data_x_span,
            'y_span': data_y_span}


def downsample(data, transform, plot_state, render_state):
    _loadAR()  # Must be called before any attempts to use AR proper
    glyphspec = transform['glyphspec']
    xcol = glyphspec['x']['field']
    ycol = glyphspec['y']['field']
    datacol = _datacolumn(glyphspec)

    if render_state == _generate_render_state(plot_state):
        logger.info("Skipping update; render state unchanged")
        return {'render_state': "NO UPDATE"}

    # Translate the resample parameters to server-side rendering....
    # TODO: Do more to preserve the 'natural' data form and have make_glyphset build the 'right thing' (tm)

    if not isinstance(data, dict):
        columns = [xcol, ycol] + ([datacol] if datacol else [])
        data = data.select(columns=columns)

    xcol = data[xcol]
    ycol = data[ycol]
    datacol = data[datacol] if datacol else np.zeros_like(xcol)
    glyphs = make_glyphset(xcol, ycol, datacol, glyphspec, transform)
    shader = transform['shader']

    if shader.out == "image" or shader.out == "image_rgb":
        rslt = downsample_image(xcol, ycol, glyphs, transform, plot_state)
    elif shader.out == "poly_line":
        rslt = downsample_line(xcol, ycol, glyphs, transform, plot_state)
    else:
        raise ValueError("Unhandled shader output '{0}.".format(shader.out))

    rslt['render_state'] = _generate_render_state(plot_state)

    return rslt


def downsample_line(xcol, ycol, glyphs, transform, plot_state):
    logger.info("Starting line-producing downsample")
    screen_x_span = float(_span(plot_state['screen_x']))
    screen_y_span = float(_span(plot_state['screen_y']))
    data_x_span = float(_span(plot_state['data_x']))
    data_y_span = float(_span(plot_state['data_y']))
    shader = transform['shader']

    if data_x_span == 0 or data_y_span == 0:
        # How big would a full plot of the data be at the current resolution?
        # If scale is zero for either axis, don't actual render,
        # instead report back data bounds and wait for the next request
        # This enables guide creation...which changes the available plot size.
        plot_size = [screen_x_span, screen_y_span]
        parts = shader.reformat(None)
    else:
        bounds = glyphs.bounds()
        plot_size = [bounds[2], bounds[3]]
        balancedZoom = transform.get('balancedZoom', False)

        vt = util.zoom_fit(plot_size, bounds, balanced=balancedZoom)

        lines = ar.render(glyphs,
                          transform['info'].reify(),
                          transform['agg'].reify(glyphset=glyphs),
                          shader.reify(),
                          plot_size, vt)

        parts = shader.reformat(lines, xcol.min(), ycol.min())

    parts['x_range'] = {'start': xcol.min(), 'end': xcol.max()}
    parts['y_range'] = {'start': ycol.min(), 'end': ycol.max()}

    logger.info("Finished line-producing downsample")
    return parts


def downsample_image(xcol, ycol, glyphs, transform, plot_state):
    logger.info("Starting image-producing downsample")
    screen_x_span = float(_span(plot_state['screen_x']))
    screen_y_span = float(_span(plot_state['screen_y']))
    data_x_span = float(_span(plot_state['data_x']))
    data_y_span = float(_span(plot_state['data_y']))
    shader = transform['shader']
    balanced_zoom = transform.get('balancedZoom', False)

    if data_x_span == 0 or data_y_span == 0:
        # How big would a full plot of the data be at the current resolution?
        # If scale is zero for either axis, don't actual render,
        # instead report back data bounds and wait for the next request
        # This enables guide creation...which changes the available plot size.
        image = shader.reformat(None)
        if balanced_zoom:
            bounds = glyphs.bounds()
            scale_x = 1
            scale_y = (bounds[2]/bounds[3])/(screen_x_span/screen_y_span)
        else:
            scale_x = 1
            scale_y = 1
    else:
        bounds = glyphs.bounds()
        scale_x = data_x_span/screen_x_span
        scale_y = data_y_span/screen_y_span
        plot_size = (bounds[2]/scale_x, bounds[3]/scale_y)

        vt = util.zoom_fit(plot_size, bounds, balanced=False)
        (tx, ty, sx, sy) = vt

        image = ar.render(glyphs,
                          transform['info'].reify(),
                          transform['agg'].reify(glyphset=glyphs),
                          shader.reify(),
                          plot_size, vt)

        image = shader.reformat(image)

    rslt = {'image': [image],
            'global_offset_x': [0],
            'global_offset_y': [0],

            # Screen-mapping values.
            # x_range is the left and right data space values corresponding to
            #     the bottom left and bottom right of the plot
            # y_range is the bottom and top data space values corresponding to
            #     the bottom left and top left of the plot
            'x_range': {'start': xcol.min()*scale_x,
                        'end': xcol.max()*scale_x},
            'y_range': {'start': ycol.min()*scale_y,
                        'end': ycol.max()*scale_y},

            # Data-image parameters.
            # x/y are lower left data-space coord of the image.
            # dw/dh are the width and height in data space
            'x': [xcol.min()],
            'y': [ycol.min()],
            'dw': [xcol.max()-xcol.min()],
            'dh': [ycol.max()-ycol.min()]
            }

    logger.info("Finished image-producing downsample")
    return rslt


def _datacolumn(glyphspec):
    """Search the glyphspec to determine what the data column is.
    Returns the column name or False if none was found

    Precedence:
    Type > Fill Color > Fill Alpha > Line Color > Line Alpha

    TODO: Support a tuple-like datacolumn
    TODO: Support direct AR override parameter to directly specify data column
    TODO: Line width?
    """

    def maybe_get(key):
        return (key in glyphspec
                and isinstance(glyphspec[key], dict)
                and glyphspec[key].get('field', False))

    return (maybe_get('type')
            or maybe_get('fill_color')
            or maybe_get('fill_alpha')
            or maybe_get('line_color')
            or maybe_get('line_alpha'))


def _span(r):
    """Distance in a Range1D"""
    end = r.end if r.end is not None else 0
    start = r.start if r.start is not None else 0
    return abs(end-start)


def _shaper(glyphspec, points):
    """Construct the AR shaper to match the given shape code."""
    code = glyphspec['type']
    code = code.lower()

    tox = glyphset.idx(0)
    toy = glyphset.idx(1)

    if points:
        sizer = glyphset.const(1)
        return glyphset.ToPoint(tox, toy, sizer, sizer)

    if code == 'square':
        size = glyphspec['size'].get('default', 1)
        sizer = glyphset.const(size)
        return glyphset.ToRect(tox, toy, sizer, sizer)
    if code == 'circle':
        size = glyphspec['radius'].get('default', 1)
        sizer = glyphset.const(size)
        return glyphset.ToRect(tox, toy, sizer, sizer)
    else:
        raise ValueError("Unrecogized shape, received '{0}'".format(code))


# -------------------- Recipes -----------------------

def hdalpha(plot, cats=None, palette=None, log=True, spread=0, **kwargs):
    """
    Produce a plot using high-definition alpha composition (HDAlpha).
    HDAlpha essentially makes a heatmap for each of a number of categories,
    with different colors for each category.  Then those colors are composed
    in a way that ensures that oversaturate on does not occur.
    This is a convenience function that encodes a common configuration,
    and parameters to support the most common variations.

    plot -- Plot to convert into an HDAlpha plot
    cats -- What are the expected categories?
                 Default is None, indicating that categories
                 should be determined automatically.
    palette -- What colors should be used. Colors are matched to categories in
              order, so the first color is associated with the first category.
              Default is a rainbow palette with 8 steps.
    spread -- How far (if any) should values be spread. Default is 0.
    long -- Log-transform each category prior to composing? Default is True.
    kwargs -- Further arguments passed on to replot for greater control.

    Note: Category to color association follows the rules of the HDAlpha
         operator.  Refer to that documentation for corner case resolution.
    """

    if cats is None:
        info = AutoEncode()
    else:
        info = Encode(cats=cats)

    if palette is None:
        palette = ["#e41a1c", "#377eb8", "#4daf4a", "#984ea3", "#ff7f00", "#ffff33", "#a65628", "#f781bf"]

    kwargs['points'] = kwargs.get('points', True)

    return replot(plot,
                  info=info,
                  agg=CountCategories(),
                  shader=Spread(factor=spread) + HDAlpha(colors=palette, log=log),
                  **kwargs)


def heatmap(plot,
            client_color=False,
            low=(255, 200, 200), high=(255, 0, 0),
            spread=0, transform="cbrt", **kwargs):
    """
    Produce a heatmap from a set of shapes.
    A heatmap is a scale of how often a single thing occurs.
    This is a convenience function that encodes a common configuration,
    and parameters to support the most common variations.


    plot -- Plot to convert into a heatmap
    low -- Low color of the heatmap.  Default is a light red
    high -- High color of the heatmap. Default is full saturation red.
    spread -- How far (if any) should values be spread. Default is 0.
    transform -- Apply a transformation before building a color ramp?
                 Understood values are 'cbrt', 'log', 'none' and None.
                 The default is 'cbrt', for cuberoot, an approximation of
                 perceptual correction on monochromatic scales.
    kwargs -- Further arguments passed on to replot for greater control.
    """

    transform = transform.lower() if transform is not None else None

    if client_color:
        shader = Id()
        kwargs['reserve_val'] = kwargs.get('reserve_val', 0)
    else:
        shader = InterpolateColor(low=low, high=high)

    if transform == "cbrt":
        shader = Cuberoot() + shader
    elif transform == "log":
        shader = Log() + shader
    elif transform == "none" or transform is None:
        pass
    else:
        raise ValueError("Unrecognized transform '{0}'".format(transform))

    if spread > 0:
        shader = Spread(factor=spread, shape="circle") + shader

    kwargs['points'] = kwargs.get('points', True)

    return replot(plot,
                  agg=Count(),
                  info=Const(val=1),
                  shader=shader,
                  **kwargs)


def contour(plot, palette=None, transform='cbrt', spread=0, **kwargs):
    """
    Create ISO contours from a given plot

    plot -- Plot to convert into iso contours
    spread -- How far (if any) should values be spread. Default is 0.
    palette -- What should the line colors be?
               The number of lines is determined by the number of colors.
    transform -- Apply a transformation before building the iso contours?
                 Understood values are 'cbrt', 'log', 'none' and None.
                 The default is 'cbrt', for cuberoot, an approximation of
                 perceptual correction for monochromatic scales.
    kwargs -- Further arguments passed on to replot for greater control.
    """
    if palette is None:
        palette = ["#C6DBEF", "#9ECAE1", "#6BAED6", "#4292C6", "#2171B5", "#08519C", "#08306B"]

    shader = Contour(levels=len(palette))

    if transform == "cbrt":
        shader = Cuberoot() + shader
    elif transform == "log":
        shader = Log() + shader
    elif transform == "none" or transform is None:
        pass
    else:
        raise ValueError("Unrecognized transform '{0}'".format(transform))

    if spread > 0:
        shader = Spread(factor=spread, shape="circle") + shader

    return replot(plot,
                  agg=Count(),
                  info=Const(val=1),
                  shader=shader,
                  line_color=palette,
                  **kwargs)
