# Hawa user guide

Hawa is a **CFD sketchpad** for Rhino 8 and Grasshopper. It gives quick, approximate
lattice Boltzmann flow around your Rhino geometry, inside Rhino. It is experimental
and is not an engineering solver: a successful run or an attractive field does not
establish convergence or engineering accuracy.

## Start here

1. **Install and first run:** [plugin guide](../plugin.md#install). Quit Rhino
   normally before replacing an installed build.
2. **Set up a case in the native panel:** [0.5 native guide](../native-v0.5.md).
   Select closed meshes or solid Breps, set the domain and cell size, then solve.
3. **Build workflows in Grasshopper:** [editable example definitions](../../examples/grasshopper/README.md).
   Example 10 is the supported hull search.

## Topics

- [Domains inside domains](../parent-child-domains.md): parent and child domains,
  overlap rules and memory budgets.
- [Moving bodies](../moving-surfaces-v0.4.md): prescribed motion and body loads, with
  their limits.
- [Boundaries](../general-boundaries.md) and [mapped boundary transfer](../boundary-transfer.md).
- [Curved walls](../curved-boundaries-v0.5.md): the experimental stationary option.

## Reading results

Fields are sampled on the computational lattice. Cell size limits how well thin
features and curved surfaces are represented, so check the solver geometry before
trusting near-wall flow. Quality labels describe the run's numerical envelope, not
engineering validation.

Developer and project records are separate. See [CONTRIBUTING](../../CONTRIBUTING.md).
