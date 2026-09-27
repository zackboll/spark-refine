package body Fixed_Pool with SPARK_Mode is

   ----------------
   -- Free_Model --
   ----------------

   --  The derived model, its cardinality and membership relations and the
   --  loop that builds it all come from the reusable library.
   function Free_Model (P : Pool) return Id_Sets.Set is
     (Free_Prefix.Model (P.Free_Stack, P.Top));

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
      P.Top := P.Top + 1;
      P.Free_Stack (P.Top) := Id;
   end Release;

end Fixed_Pool;
