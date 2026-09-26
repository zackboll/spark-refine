package body Ring_Buffer with SPARK_Mode is

   -----------
   -- Model --
   -----------

   --  Derived model: logical element K (1-based) is the physical slot at
   --  offset K - 1 from Head. Built from Head and Count only; Tail is
   --  redundant production state. Ghost: never compiled into the executable.

   function Model (B : Buffer) return Sequences.Sequence
   with Refined_Post =>
     Sequences.Last (Model'Result) = B.Count
     and then (for all K in 1 .. B.Count =>
                 Sequences.Get (Model'Result, K)
                 = B.Content (Physical_Index (B.Head, K - 1)))
   is
      R : Sequences.Sequence;
   begin
      for J in 1 .. B.Count loop
         R := Sequences.Add (R, B.Content (Physical_Index (B.Head, J - 1)));
         pragma Loop_Invariant (Sequences.Last (R) = J);
         pragma Loop_Invariant
           (for all K in 1 .. J =>
              Sequences.Get (R, K)
              = B.Content (Physical_Index (B.Head, K - 1)));
      end loop;
      return R;
   end Model;

   --------------
   -- Is_Empty --
   --------------

   function Is_Empty (B : Buffer) return Boolean is (B.Count = 0);

   -------------
   -- Is_Full --
   -------------

   function Is_Full (B : Buffer) return Boolean is (B.Count = Max_Size);

   ----------------
   -- Initialize --
   ----------------

   procedure Initialize (B : out Buffer) is
   begin
      B := (Content => [others => 0],
            Head    => Storage_Index'First,
            Tail    => Storage_Index'First,
            Count   => 0);
   end Initialize;

   -----------
   -- Clear --
   -----------

   procedure Clear (B : in out Buffer) is
   begin
      B.Head  := Storage_Index'First;
      B.Tail  := Storage_Index'First;
      B.Count := 0;
   end Clear;

   ----------
   -- Push --
   ----------

   procedure Push (B : in out Buffer; E : Element) is
   begin
      B.Content (B.Tail) := E;
      B.Tail  := Physical_Index (B.Tail, 1);
      B.Count := B.Count + 1;
   end Push;

   ---------
   -- Pop --
   ---------

   procedure Pop (B : in out Buffer; E : out Element) is
   begin
      E := B.Content (B.Head);
      B.Head  := Physical_Index (B.Head, 1);
      B.Count := B.Count - 1;
   end Pop;

   ----------
   -- Peek --
   ----------

   procedure Peek (B : Buffer; E : out Element) is
   begin
      E := B.Content (B.Head);
   end Peek;

end Ring_Buffer;
