package body Fixed_Pool with SPARK_Mode is

   ----------------
   -- Free_Model --
   ----------------

   function Free_Model (P : Pool) return Id_Sets.Set
   with Refined_Post =>
     Id_Sets.Length (Free_Model'Result) = To_Big_Integer (P.Top)
     and (for all Id in Object_Id =>
            Id_Sets.Contains (Free_Model'Result, Id)
            = (for some I in 1 .. P.Top => P.Free_Stack (I) = Id))
   is
      R : Id_Sets.Set;
   begin
      for I in 1 .. P.Top loop
         R := Id_Sets.Add (R, P.Free_Stack (I));
         pragma Loop_Invariant (Id_Sets.Length (R) = To_Big_Integer (I));
         pragma Loop_Invariant
           (for all Id in Object_Id =>
              Id_Sets.Contains (R, Id)
              = (for some K in 1 .. I => P.Free_Stack (K) = Id));
      end loop;
      return R;
   end Free_Model;

   --------------------------
   -- Lemma_Universe_Bound --
   --------------------------

   --  Finite-universe (pigeonhole) bound: no set of identities has more
   --  than Max_Objects elements. The universe U is the model of the full
   --  identity stack, so Length (U) = Max_Objects and S <= U by
   --  Free_Model'Refined_Post; SPARKlib's Num_Overlaps contract then gives
   --  Length (S) = Num_Overlaps (S, U) <= Length (U).
   procedure Lemma_Universe_Bound (S : Id_Sets.Set)
   with Ghost,
        Global => null,
        Post   => Id_Sets.Length (S) <= To_Big_Integer (Max_Objects)
   is
      U : constant Id_Sets.Set :=
        Free_Model ((Free_Stack => [for I in Object_Id => I],
                     Top        => Max_Objects));
   begin
      pragma Assert (Id_Sets.Num_Overlaps (S, U) = Id_Sets.Length (S));
   end Lemma_Universe_Bound;

   ----------------
   -- Free_Count --
   ----------------

   function Free_Count (P : Pool) return Pool_Count is (P.Top);

   -------------
   -- Is_Free --
   -------------

   function Is_Free (P : Pool; Id : Object_Id) return Boolean is
     (for some I in 1 .. P.Top => P.Free_Stack (I) = Id);

   ------------------
   -- Is_Allocated --
   ------------------

   function Is_Allocated (P : Pool; Id : Object_Id) return Boolean is
     (not Is_Free (P, Id));

   ------------------
   -- Is_Exhausted --
   ------------------

   function Is_Exhausted (P : Pool) return Boolean is (P.Top = 0);

   ----------------
   -- Initialize --
   ----------------

   procedure Initialize (P : out Pool) is
   begin
      P := (Free_Stack => [for I in Object_Id => I],
            Top        => Max_Objects);
   end Initialize;

   --------------
   -- Allocate --
   --------------

   procedure Allocate (P : in out Pool; Id : out Object_Id) is
   begin
      Id := P.Free_Stack (P.Top);
      P.Top := P.Top - 1;
   end Allocate;

   -------------
   -- Release --
   -------------

   procedure Release (P : in out Pool; Id : Object_Id) is
   begin
      Lemma_Universe_Bound (Id_Sets.Add (Free_Model (P), Id));
      P.Top := P.Top + 1;
      P.Free_Stack (P.Top) := Id;
   end Release;

end Fixed_Pool;
