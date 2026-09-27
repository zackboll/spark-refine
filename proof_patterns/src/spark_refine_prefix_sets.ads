with SPARK.Big_Integers; use SPARK.Big_Integers;
with SPARK.Containers.Functional.Sets;

--  Reusable proof pattern (Task 004): a unique active prefix of a bounded
--  array, read as a mathematical set over a finite identity universe.
--
--     Storage (Index_Type'First .. Prefix_Last (Count))   (the active prefix)
--        |  Is_Unique: no identity occurs twice
--        v
--     Model (Storage, Count) : Element_Sets.Set
--        Length   (Model) = Count
--        Contains (Model, E) = In_Prefix (Storage, Count, E)
--        Count < Universe_Size, or every identity is in the prefix
--
--  plus the same finite-universe (pigeonhole) fact for arbitrary sets,
--  Lemma_Can_Add.
--
--  Hand-written, ordinary SPARK. Nothing here is generated. Every entity
--  is Ghost, so nothing executes when assertions are disabled. The package
--  itself is not Ghost: a Ghost generic turns Element_Sets into a ghost
--  formal package, and GNAT then rejects the caller's (non-ghost, public)
--  set instance as actual ("ghost package expected for actual").
--
--  Version-1 restrictions (deliberate, see docs/PROOF_PATTERNS.md):
--    * the active prefix starts at Index_Type'First;
--    * Count is the prefix length (0 .. number of storage positions);
--    * Element_Type is a discrete type (finite universe), and the caller's
--      Functional.Sets instance must use predefined "=" as equivalence;
--    * Element_Type'Pos range and Index_Type range must fit in Integer
--      (range checks on the conversions are proved per instance).
--
--  GNATprove proves generic code per instance: every instantiation re-proves
--  this package's body for its own actuals. What is reused is the authoring
--  of the proof, not its execution.

generic
   type Element_Type is (<>);
   --  Identity universe (finite and discrete)

   type Index_Type is range <>;
   --  Storage positions (independent of the identity type)

   type Storage_Array is array (Index_Type) of Element_Type;

   with package Element_Sets is new SPARK.Containers.Functional.Sets
     (Element_Type => Element_Type, Equivalent_Elements => "=", others => <>);
   --  The caller's existing mathematical set instance

package SPARK_Refine_Prefix_Sets
  with SPARK_Mode, Always_Terminates
is

   subtype Count_Type is Index_Type'Base
     range 0 .. Index_Type'Last - Index_Type'First + 1;
   --  Length of the active prefix

   function Prefix_Last (Count : Count_Type) return Index_Type'Base is
     (Index_Type'First + (Count - 1))
   with Ghost;
   --  Last active position (Index_Type'First - 1 when Count = 0)

   function In_Prefix
     (Storage : Storage_Array; Count : Count_Type; E : Element_Type)
      return Boolean
   is (for some I in Index_Type'First .. Prefix_Last (Count) =>
         Storage (I) = E)
   with Ghost;

   function Is_Unique
     (Storage : Storage_Array; Count : Count_Type) return Boolean
   is (for all I in Index_Type'First .. Prefix_Last (Count) =>
         (for all J in Index_Type'First .. I - 1 =>
            Storage (I) /= Storage (J)))
   with Ghost;
   --  No identity occurs twice in the active prefix

   function Universe_Size return Big_Natural is
     (To_Big_Integer ((Element_Type'Pos (Element_Type'Last)
                       - Element_Type'Pos (Element_Type'First)) + 1))
   with Ghost;
   --  Number of values of Element_Type

   function Model
     (Storage : Storage_Array; Count : Count_Type) return Element_Sets.Set
   with Ghost,
        Global => null,
        Pre    => Is_Unique (Storage, Count),
        Post   =>
          Element_Sets.Length (Model'Result) = To_Big_Integer (Integer (Count))
          and (for all E in Element_Type =>
                 Element_Sets.Contains (Model'Result, E)
                 = In_Prefix (Storage, Count, E))
          and (To_Big_Integer (Integer (Count)) < Universe_Size
               or else (for all E in Element_Type =>
                          In_Prefix (Storage, Count, E)));
   --  The active prefix as a set: exactly its elements, one per position.
   --  Finite universe: either there is room for another identity, or the
   --  prefix already holds every identity. (So a caller that knows some E
   --  is missing gets Count < Universe_Size without calling a lemma.)

   procedure Lemma_Can_Add (S : Element_Sets.Set; E : Element_Type)
   with Ghost,
        Global => null,
        Pre    => not Element_Sets.Contains (S, E),
        Post   => Element_Sets.Length (S) < Universe_Size;
   --  Finite universe: if some identity is missing from S, then S is
   --  strictly smaller than the universe (room for one more element).

end SPARK_Refine_Prefix_Sets;
