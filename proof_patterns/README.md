# SPARK proof-pattern library (Task 004)

Hand-written, reusable SPARK generics that carry recurring *refinement
proof* knowledge, so that applications do not re-derive it. Nothing here
is generated.

## `SPARK_Refine_Prefix_Sets`

A unique active prefix of a bounded array, read as a
`SPARK.Containers.Functional.Sets` set over a finite identity type.

```ada
private with SPARK_Refine_Prefix_Sets;
...
private
   package Free_Prefix is new SPARK_Refine_Prefix_Sets
     (Element_Type  => Object_Id,      --  finite discrete identity type
      Index_Type    => Object_Id,      --  storage positions (may differ)
      Storage_Array => Free_Array,     --  array (Index_Type) of Element_Type
      Element_Sets  => Id_Sets);       --  your existing Functional.Sets instance

   type Pool is record ... end record
   with Type_Invariant => Free_Prefix.Is_Unique (Pool.Free_Stack, Pool.Top);

--  body
function Free_Model (P : Pool) return Id_Sets.Set is
  (Free_Prefix.Model (P.Free_Stack, P.Top));
```

`Model`'s contract gives:

* `Length = Count`;
* `Contains (Model, E) = In_Prefix (Storage, Count, E)`;
* the finite-universe fact: `Count < Universe_Size`, or every identity is
  in the prefix.

So pushing an identity that is not free needs no lemma call.
`Lemma_Can_Add` covers sets not built from a prefix.

Version-1 restrictions:

* the prefix starts at `Index_Type'First`;
* the count is the prefix length, of type `Index_Type'Base`;
* `Element_Type` is discrete, with predefined `=` as the set's
  equivalence;
* positions fit in `Integer`.

## Trust and proof

* No `pragma Assume`, axioms, justifications, imports or suppression.
  This is gated by `examples/fixed_pool/scripts/check_proof_results.py
  trust-scan`.
* The only foundation is the SPARKlib `Functional.Sets` / `Big_Integers`
  contracts.
* GNATprove proves generics **per instance**. CI proves the pool instance
  and the three validation instances in `validation/`:
  `python3 examples/fixed_pool/scripts/check_proof_results.py
  library-validation`.
* No claim is made for instances that are not proved.
