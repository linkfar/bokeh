import {Range} from "./range"
import * as p from "core/properties"
import {all, sum} from "core/util/array"
import {keys} from "core/util/object"
import {isArray, isNumber, isString} from "core/util/types"

_map_one = (factors, padding) ->
  mapping = {}

  for f, i in factors
    if f == null
      throw new Error("")
    if f of mapping
      throw new Error("")
    mapping[f] = {value: 0.5 + i*(1+padding)}

  return [mapping, (factors.length-1)*padding]

_map_two = (factors, padding, offset=0) ->
  mapping = {}

  tops = {}
  for [f0, f1], i in factors
    if f0 == null
      throw new Error("")

    if f0 not of tops
      tops[f0] = []
    tops[f0].push(0.5 + i*(1+padding))

  seen = {}
  for [f0, f1], i in factors
    seen[f0] = 1
    if f0 not of mapping
      avg = sum(tops[f0]) / tops[f0].length
      mapping[f0] = {value: avg + offset, mapping: {}}

    if f1 of mapping[f0].mapping
      throw new Error("")

    if f1 != null
      n = keys(seen).length - 1
      mapping[f0].mapping[f1] = {value: 0.5 + i + n*padding + offset}

  return [mapping, (keys(seen).length - 1)*padding]

_map_three = (factors, padding) ->
  mapping = {}

  tops = {}
  tops_order = []
  for [f0, f1, f2], i in factors
    if f0 == null or f1 == null
      throw new Error("")

    if f0 not of tops
      tops[f0] = []
      tops_order.push(f0)
    tops[f0].push([f1, f2])

  offset = 0
  total_subpadding = 0
  for f0, i in tops_order
    n = tops[f0].length
    [submap, subpad] = _map_two(tops[f0], padding, offset)
    total_subpadding += subpad
    subtotal = 0
    for k of submap
      subtotal += submap[k].value
    mapping[f0] = {value: subtotal/n, mapping: submap}
    offset += (n + padding + subpad)

  return [mapping, (tops_order.length-1)*padding + total_subpadding]

export class FactorRange extends Range
  type: 'FactorRange'

  @define {
    factors:             [ p.Array,        []        ]
    factor_padding:      [ p.Number,       0         ]
    range_padding:       [ p.Number,       0.1       ]
    range_padding_units: [ p.PaddingUnits, "percent" ]
    start:               [ p.Number                  ]
    end:                 [ p.Number                  ]
  }

  @getters {
    min: () -> @start
    max: () -> @end
  }

  initialize: (attrs, options) ->
    super(attrs, options)
    @_init()
    @connect(@properties.factors.change, () -> @_init())

  reset: () ->
    @_init()
    @change.emit()

  # convert a string factor into a synthetic coordinate
  synthetic: (x) ->
    if isNumber(x)
      return x

    if isString(x)
      return @_lookup([x])

    offset = 0
    if isNumber(x[x.length-1])
      offset = x[x.length-1]
      x = x.slice(0,-1)

    return @_lookup(x) + offset

  # convert an array of string factors into synthetic coordinates
  v_synthetic: (xs) ->
    result = (@synthetic(x) for x in xs)

  _init: () ->

    if all(@factors, isString)
      [@_mapping, inside_padding] = _map_one(@factors, @factor_padding)

    else if all(@factors, (x) -> isArray(x) and x.length==2)
      [@_mapping, inside_padding] = _map_two(@factors, @factor_padding)

    else if all(@factors, (x) -> isArray(x) and x.length==3)
      [@_mapping, inside_padding] = _map_three(@factors, @factor_padding)

    else
      throw new Error("")

    start = 0
    end = @factors.length + inside_padding

    if @range_padding_units == "percent"
      half_span = (end - start) * @range_padding / 2
      start -= half_span
      end += half_span
    else
      start -= @range_padding
      end += range_padding

    @setv({start: start, end: end}, {silent: true})

  _lookup: (x) ->
    if x.length == 1
      return @_mapping[x[0]].value

    else if x.length == 2
      return @_mapping[x[0]].mapping[x[1]].value

    else if x.length == 3
      return @_mapping[x[0]].mapping[x[1]].mapping[x[2]].value
