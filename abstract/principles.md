# Design principles

Scope: the questions section 3 of every base standard opens with, in this order. When two rules
appear to conflict and their tiers are equal, a standard breaks the tie by asking them in turn, each
answered in its own domain's terms; questions a standard adds of its own follow them.

1. **What can be deleted?** Fewer types, parameters, states and dependencies, so that each part left
   earns its place.
2. **What can be made unrepresentable?** Push an invariant into the type, so that an invalid state
   cannot be built rather than being rejected where it is met.
3. **What can be made a value instead of an effect?** Prefer a function that returns what should
   change over one that changes it, and leave applying the change to one place.
4. **What is asymmetric?** Operations that come in pairs have both halves, siblings take their
   arguments in one order, and a missing half is either a restriction to state or an oversight.
5. **What is special-cased?** A branch that exists for one input is a design that has not absorbed
   it: fold it into the general case, or give it its own type.
