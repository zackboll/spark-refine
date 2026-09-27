package body SPARK_Refine_Prefix_Sets with SPARK_Mode is

   --------------------------
   -- Lemma_Universe_Bound --
   --------------------------

   --  Pigeonhole: every set over Element_Type has at most Universe_Size
   --  elements, and a set of exactly that size is the whole universe.
   --  U is built to contain every identity, so S <= U and SPARKlib's
   --  Num_Overlaps contract gives Length (S) = Num_Overlaps (S, U)
   --  <= Length (U) = Universe_Size, with equality only if U <= S.
   procedure Lemma_Universe_Bound (S : Element_Sets.Set)
   with Ghost,
        Global => null,
        Post   => Element_Sets.Length (S) <= Universe_Size
                  and (if Element_Sets.Length (S) = Universe_Size
                       then (for all E in Element_Type =>
                               Element_Sets.Contains (S, E)))
   is
      U : Element_Sets.Set;
   begin
      for E in Element_Type loop
         U := Element_Sets.Add (U, E);
         pragma Loop_Invariant
           (Element_Sets.Length (U)
            = To_Big_Integer ((Element_Type'Pos (E)
                               - Element_Type'Pos (Element_Type'First)) + 1));
         pragma Loop_Invariant
           (for all X in Element_Type =>
              Element_Sets.Contains (U, X) = (X <= E));
      end loop;
      pragma Assert (Element_Sets.Num_Overlaps (S, U)
                     = Element_Sets.Length (S));
   end Lemma_Universe_Bound;

   -----------
   -- Model --
   -----------

   function Model
     (Storage : Storage_Array; Count : Count_Type) return Element_Sets.Set
   is
      R : Element_Sets.Set;
   begin
      for I in Index_Type'First .. Prefix_Last (Count) loop
         --  Is_Unique: Storage (I) is not yet in R
         R := Element_Sets.Add (R, Storage (I));
         pragma Loop_Invariant
           (Element_Sets.Length (R)
            = To_Big_Integer (Integer ((I - Index_Type'First) + 1)));
         pragma Loop_Invariant
           (for all E in Element_Type =>
              Element_Sets.Contains (R, E)
              = (for some K in Index_Type'First .. I => Storage (K) = E));
      end loop;
      Lemma_Universe_Bound (R);
      return R;
   end Model;

   -------------------
   -- Lemma_Can_Add --
   -------------------

   procedure Lemma_Can_Add (S : Element_Sets.Set; E : Element_Type) is
   begin
      Lemma_Universe_Bound (S);
   end Lemma_Can_Add;

end SPARK_Refine_Prefix_Sets;
