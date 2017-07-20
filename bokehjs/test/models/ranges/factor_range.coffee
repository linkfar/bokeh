{expect} = require "chai"
utils = require "../../utils"
sinon = require "sinon"

{CustomJS} = utils.require("models/callbacks/customjs")
{FactorRange} = utils.require("models/ranges/factor_range")

describe "factor_range module", ->

  describe "default creation", ->
    r = new FactorRange()

    it "should have empty factors", ->
      expect(r.factors).to.be.deep.equal []

    it "should have start=0", ->
      expect(r.start).to.be.equal 0

  describe "reset method", ->

    it "should execute callback once", ->
      cb = new CustomJS()
      r = new FactorRange({callback: cb})
      spy = sinon.spy(cb, 'execute')
      r.reset()

      expect(spy.calledOnce).to.be.true

  describe "changing model attribute", ->

    it "should execute callback once", ->
      cb = new CustomJS()
      spy = sinon.spy(cb, 'execute')
      r = new FactorRange({callback: cb})

      expect(spy.called).to.be.false
      r.factors = ["A", "B", "C"]
      expect(spy.calledOnce).to.be.true

  describe "simple list of factors", ->

    describe "validation", ->

      it "should throw an error on duplicate factors", ->
        expect(() -> new FactorRange({factors: ['a', 'a']})).to.throw(Error)

      it "should throw an error on null factors", ->
        expect(() -> new FactorRange({factors: [null]})).to.throw(Error)

    describe "min/max properties", ->
      r = new FactorRange({factors: ['FOO'], range_padding: 0})

      it "should return values from synthetic range", ->

        expect(r.min).to.be.equal 0
        expect(r.max).to.be.equal 1

      it "should update when factors update", ->
        r.factors = ['FOO', 'BAR']

        expect(r.min).to.be.equal 0
        expect(r.max).to.be.equal 2

        r.factors = ['A', 'B', 'C']

        expect(r.min).to.be.equal 0
        expect(r.max).to.be.equal 3

      it "min should equal start", ->
        expect(r.min).to.be.equal r.start

      it "max should equal end", ->
        expect(r.max).to.be.equal r.end

    describe "start/end properties", ->
      r = new FactorRange({factors: ['FOO'], range_padding: 0})

      it "should return values from synthetic range", ->

        expect(r.min).to.be.equal 0
        expect(r.max).to.be.equal 1

      it "should update when factors update", ->
        r.factors = ['FOO', 'BAR']

        expect(r.min).to.be.equal 0
        expect(r.max).to.be.equal 2

        r.factors = ['A', 'B', 'C']

        expect(r.min).to.be.equal 0
        expect(r.max).to.be.equal 3

    describe "synthetic method", ->
      r = new FactorRange({factors: ['A', 'B', 'C']})

      it "should return numeric offsets as-is", ->
        expect(r.synthetic(10)).to.equal 10
        expect(r.synthetic(10.2)).to.equal 10.2
        expect(r.synthetic(-5.7)).to.equal -5.7
        expect(r.synthetic(-5)).to.equal -5

      it "should map simple factors to synthetic coords", ->
        expect(r.synthetic("A")).to.equal 0.5
        expect(r.synthetic("B")).to.equal 1.5
        expect(r.synthetic("C")).to.equal 2.5

      it "should map simple factors with offsets to synthetic coords", ->
        expect(r.synthetic(["A", 0.1])).to.equal 0.6
        expect(r.synthetic(["B", -0.2])).to.equal 1.3
        expect(r.synthetic(["C"])).to.equal 2.5

      it "should not modify inputs", ->
        x = ["B", -0.2]
        r.synthetic(x)
        expect(x).to.deep.equal ["B", -0.2]

    describe "v_synthetic method", ->
      r = new FactorRange({factors: ['A', 'B', 'C']})

      it "should return an Array", ->
        x = r.v_synthetic([10, 10.2, -5.7, -5])
        expect(x).to.be.instanceof(Array)
        x = r.v_synthetic(["A", "B", "C", "A"])
        expect(x).to.be.instanceof(Array)
        x = r.v_synthetic([])
        expect(x).to.be.instanceof(Array)

      it "should return lists of numeric offsets as-is", ->
        x = r.v_synthetic([10, 10.2, -5.7, -5])
        expect(x).to.deep.equal [10, 10.2, -5.7, -5]

      it "should map simple factors to synthetic coords", ->
        expect(r.v_synthetic(["A", "B", "C", "A"])).to.deep.equal [0.5, 1.5, 2.5, 0.5]

      it "should map simple factors with offsets to synthetic coords", ->
        expect(r.v_synthetic([["A", 0.1], ["B", -0.2], ["C"], ["A", 0]])).to.deep.equal [0.6, 1.3, 2.5, 0.5]

      it "should not modify inputs", ->
        x = [["A", 0.1], ["B", -0.2]]
        r.v_synthetic(x)
        expect(x).to.deep.equal [["A", 0.1], ["B", -0.2]]

  describe "tuple list of factors", ->

     describe "validation", ->

      it "should throw an error on duplicate factors", ->
        expect(() -> new FactorRange({factors: [['a', '1'], ['a', '1']]})).to.throw(Error)

      it "should throw an error on null first-level factors", ->
        expect(() -> new FactorRange({factors: [[null, 'a']]})).to.throw(Error)
        expect(() -> new FactorRange({factors: [[null, null]]})).to.throw(Error)

      it "should allow null on second-level factors", ->
        expect(() -> new FactorRange({factors: [['a', null]]})).to.not.throw(Error)

    describe "min/max properties", ->
      r = new FactorRange({factors: [['FOO', 'a']], range_padding: 0})

      it "should return values from synthetic range", ->

        expect(r.min).to.be.equal 0
        expect(r.max).to.be.equal 1

      it "should update when factors update", ->
        r.factors = [['FOO', 'a'], ['BAR', 'b']]

        expect(r.min).to.be.equal 0
        expect(r.max).to.be.equal 2

        r.factors = [['A', '1'], ['A', '2'], ['C', '1']]

        expect(r.min).to.be.equal 0
        expect(r.max).to.be.equal 3

      it "min should equal start", ->
        expect(r.min).to.be.equal r.start

      it "max should equal end", ->
        expect(r.max).to.be.equal r.end

    describe "start/end properties", ->
      r = new FactorRange({factors: [['FOO', 'a']], range_padding: 0})

      it "should return values from synthetic range", ->

        expect(r.min).to.be.equal 0
        expect(r.max).to.be.equal 1

      it "should update when factors update", ->
        r.factors = [['FOO', 'a'], ['BAR', 'b']]

        expect(r.min).to.be.equal 0
        expect(r.max).to.be.equal 2

        r.factors = [['A', '1'], ['A', '2'], ['C', '1']]

        expect(r.min).to.be.equal 0
        expect(r.max).to.be.equal 3

    describe "synthetic method", ->
      r = new FactorRange({factors: [['A', '1'], ['A', '2'], ['C', '1']]})

      it "should return numeric offsets as-is", ->
        expect(r.synthetic(10)).to.equal 10
        expect(r.synthetic(10.2)).to.equal 10.2
        expect(r.synthetic(-5.7)).to.equal -5.7
        expect(r.synthetic(-5)).to.equal -5

      it "should map dual factors to synthetic coords", ->
        expect(r.synthetic(['A', '1'])).to.equal 0.5
        expect(r.synthetic(['A', '2'])).to.equal 1.5
        expect(r.synthetic(['C', '1'])).to.equal 2.5

      it "should map dual factors with offsets to synthetic coords", ->
        expect(r.synthetic(['A', '1', 0.1])).to.equal 0.6
        expect(r.synthetic(['A', '2', -0.2])).to.equal 1.3
        expect(r.synthetic(['C', '1', 0.0])).to.equal 2.5

      it "should map first-level factors to average group synthetic coords", ->
        expect(r.synthetic(['A'])).to.equal 1
        expect(r.synthetic(['C'])).to.equal 2.5

        expect(r.synthetic('A')).to.equal 1
        expect(r.synthetic('C')).to.equal 2.5

      it "should map first-level factors with offsets to average group synthetic coords", ->
        expect(r.synthetic(['A', 0.1])).to.equal 1.1
        expect(r.synthetic(['C', -0.2])).to.equal 2.3
        expect(r.synthetic(['C', 0.0])).to.equal 2.5

      it "should leave empty synthetic coords for null second-level factors", ->
        r = new FactorRange({factors: [['A', '1'], ['A', '2'], ['A', null], ['A', null], ['C', '1'], ['C', null]], range_padding: 0})
        expect(r.start).to.equal 0
        expect(r.end).to.equal 6
        expect(r.synthetic(['A', '1'])).to.deep.equal 0.5
        expect(r.synthetic(['A', '2'])).to.deep.equal 1.5
        expect(r.synthetic(['C', '1'])).to.deep.equal 4.5
        expect(r.synthetic('A')).to.deep.equal 2
        expect(r.synthetic('C')).to.deep.equal 5

      it "should not modify inputs", ->
        x = ['A', '1', 0.1]
        r.synthetic(x)
        expect(x).to.deep.equal ['A', '1', 0.1]

    describe "v_synthetic method", ->
      r = new FactorRange({factors: [['A', '1'], ['A', '2'], ['C', '1']]})

      it "should return an Array", ->
        x = r.v_synthetic([10, 10.2, -5.7, -5])
        expect(x).to.be.instanceof(Array)
        x = r.v_synthetic(["A", "C", "A"])
        expect(x).to.be.instanceof(Array)
        x = r.v_synthetic([])
        expect(x).to.be.instanceof(Array)

      it "should return lists of numeric offsets as-is", ->
        x = r.v_synthetic([10, 10.2, -5.7, -5])
        expect(x).to.deep.equal [10, 10.2, -5.7, -5]

      it "should map dual factors to synthetic coords", ->
        expect(r.v_synthetic([['A', '1'], ['A', '2'], ['C', '1']])).to.deep.equal [0.5, 1.5, 2.5]

      it "should map dual factors with offsets to synthetic coords", ->
        expect(r.v_synthetic([['A', '1', 0.1], ['A', '2', -0.2], ['C', '1', 0]])).to.deep.equal [0.6, 1.3, 2.5]

      it "should map first-level factors to average group synthetic coords", ->
        expect(r.v_synthetic([['A'], ['C']])).to.deep.equal [1, 2.5]

        expect(r.v_synthetic(['A', 'C'])).to.deep.equal [1, 2.5]

      it "should map first-level factors with offsets to average group synthetic coords", ->
        expect(r.v_synthetic([['A', 0.1], ['C', -0.2], ['C', 0]])).to.deep.equal [1.1, 2.3, 2.5]

      it "should leave empty synthetic coords for null second-level factors", ->
        r = new FactorRange({factors: [['A', '1'], ['A', '2'], ['A', null], ['A', null], ['C', '1'], ['C', null]], range_padding: 0})
        expect(r.start).to.equal 0
        expect(r.end).to.equal 6
        expect(r.v_synthetic([['A', '1'], ['A', '2'], ['C', '1']])).to.deep.equal [0.5, 1.5, 4.5]
        expect(r.v_synthetic(['A', 'C'])).to.deep.equal [2, 5]

      it "should not modify inputs", ->
        x = ['A', '1', 0.1]
        r.v_synthetic([x])
        expect(x).to.deep.equal ['A', '1', 0.1]
