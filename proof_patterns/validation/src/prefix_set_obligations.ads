with SPARK.Big_Integers; use SPARK.Big_Integers;
with SPARK_Refine_Prefix_Sets;

--  Proof-only validation client for SPARK_Refine_Prefix_Sets (Task 004).
--
--  GNATprove proves generics per instance, so the library is validated by
--  instantiating it with several different actuals (see validate_*.ads) and
--  proving, for each, the facts an application actually relies on: unique
--  prefix, model cardinality, model membership, and the finite-universe
--  lemma, used through the push/pop steps of a prefix-based free list.
--  None of these subprograms is executed.

generic
   with package PS is new SPARK_Refine_Prefix_Sets (<>);
package Prefix_Set_Obligations with SPARK_Mode is

   use type PS.Element_Sets.Set;
   use type PS.Count_Type;

   --  Empty prefix: empty model
   procedure Empty_Prefix (S : PS.Storage_Array)
   with Ghost,
        Global => null,
        Post   => PS.Is_Unique (S, 0)
                  and PS.Element_Sets.Is_Empty (PS.Model (S, 0));

   --  Push a fresh identity: uniqueness is preserved, the model grows by
   --  exactly that identity, and the old count was below the universe size
   procedure Push
     (S : in out PS.Storage_Array;
      C : in out PS.Count_Type;
      E : PS.Element_Type)
   with Ghost,
        Global => null,
        Pre    => PS.Is_Unique (S, C)
                  and then not PS.Element_Sets.Contains (PS.Model (S, C), E)
                  and then C < PS.Count_Type'Last,
        Post   => PS.Is_Unique (S, C)
                  and C = C'Old + 1
                  and To_Big_Integer (Integer (C'Old)) < PS.Universe_Size
                  and PS.Model (S, C)
                      = PS.Element_Sets.Add (PS.Model (S'Old, C'Old), E);

   --  Pop the last identity: it was in the model and is removed from it
   procedure Pop
     (S : PS.Storage_Array;
      C : in out PS.Count_Type;
      E : out PS.Element_Type)
   with Ghost,
        Global => null,
        Pre    => PS.Is_Unique (S, C) and C > 0,
        Post   => PS.Is_Unique (S, C)
                  and C = C'Old - 1
                  and PS.Element_Sets.Contains (PS.Model (S, C'Old), E)
                  and PS.Model (S, C)
                      = PS.Element_Sets.Remove (PS.Model (S, C'Old), E);

   --  Pigeonhole on prefixes: a unique prefix that misses some identity is
   --  strictly shorter than the universe (from Model's contract alone)
   procedure Missing_Implies_Short
     (S : PS.Storage_Array;
      C : PS.Count_Type;
      E : PS.Element_Type)
   with Ghost,
        Global => null,
        Pre    => PS.Is_Unique (S, C) and then not PS.In_Prefix (S, C, E),
        Post   => To_Big_Integer (Integer (C)) < PS.Universe_Size;

   --  Pigeonhole on arbitrary sets (not built from a prefix): the lemma
   procedure Set_Has_Room (S : PS.Element_Sets.Set; E : PS.Element_Type)
   with Ghost,
        Global => null,
        Pre    => not PS.Element_Sets.Contains (S, E),
        Post   => PS.Element_Sets.Length (S) < PS.Universe_Size
                  and PS.Element_Sets.Length (PS.Element_Sets.Add (S, E))
                      <= PS.Universe_Size;

end Prefix_Set_Obligations;
