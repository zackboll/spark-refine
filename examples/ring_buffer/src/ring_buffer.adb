package body Ring_Buffer with SPARK_Mode is

   -----------
   -- Model --
   -----------

   --  Derived model: logical element K (1-based) is the physical slot at
   --  offset K - 1 from First. Ghost: never compiled into the executable.
   --
   --  The Refined_Post is the abstraction relation that every operation
   --  proof relies on: callers inside this package see exactly how the
   --  sequence relates to Content/First/Length, while clients only see the
   --  public contract.

   function Model (B : Buffer) return Sequences.Sequence
   with Refined_Post =>
     Sequences.Last (Model'Result) = B.Length
     and then (for all K in 1 .. B.Length =>
                 Sequences.Get (Model'Result, K)
                 = B.Content (Physical_Index (B.First, K - 1)))
   is
      R : Sequences.Sequence;
   begin
      for J in 1 .. B.Length loop
         R := Sequences.Add (R, B.Content (Physical_Index (B.First, J - 1)));
         pragma Loop_Invariant (Sequences.Last (R) = J);
         pragma Loop_Invariant
           (for all K in 1 .. J =>
              Sequences.Get (R, K)
              = B.Content (Physical_Index (B.First, K - 1)));
      end loop;
      return R;
   end Model;

   --------------
   -- Is_Empty --
   --------------

   function Is_Empty (B : Buffer) return Boolean is (B.Length = 0);

   -------------
   -- Is_Full --
   -------------

   function Is_Full (B : Buffer) return Boolean is (B.Length = Max_Size);

   ----------------
   -- Initialize --
   ----------------

   procedure Initialize (B : out Buffer) is
   begin
      B := (Content => [others => 0],
            First   => Storage_Index'First,
            Length  => 0);
   end Initialize;

   -----------
   -- Clear --
   -----------

   procedure Clear (B : in out Buffer) is
   begin
      B.First  := Storage_Index'First;
      B.Length := 0;
   end Clear;

   ----------
   -- Push --
   ----------

   procedure Push (B : in out Buffer; E : Element) is
   begin
      B.Content (Physical_Index (B.First, B.Length)) := E;
      B.Length := B.Length + 1;
   end Push;

   ---------
   -- Pop --
   ---------

   procedure Pop (B : in out Buffer; E : out Element) is
   begin
      E := B.Content (B.First);
      B.First  := Physical_Index (B.First, 1);
      B.Length := B.Length - 1;
   end Pop;

   ----------
   -- Peek --
   ----------

   procedure Peek (B : Buffer; E : out Element) is
   begin
      E := B.Content (B.First);
   end Peek;

end Ring_Buffer;
