package body Ring_Buffer with SPARK_Mode is

   --  This file intentionally stops short of the full ghost-model proof.
   --  Phase 1 of the project is to implement the manual baseline here,
   --  measure its proof-support code, and only then build the generator.

   function Model (B : Buffer) return Model_Array is
      pragma Unreferenced (B);
   begin
      --  Bootstrap placeholder only. This is not the final model and this
      --  example is not yet a proof fixture.
      return [1 .. 0 => 0];
   end Model;

   function Is_Empty (B : Buffer) return Boolean is (B.Length = 0);
   function Is_Full  (B : Buffer) return Boolean is (B.Length = Max_Size);

   procedure Push (B : in out Buffer; E : Element) is
      Write_Pos : Storage_Index;
   begin
      Write_Pos := Storage_Index
        (((Integer (B.First) - 1 + Integer (B.Length)) mod Max_Size) + 1);
      B.Content (Write_Pos) := E;
      B.Length := B.Length + 1;
   end Push;

   procedure Pop (B : in out Buffer; E : out Element) is
   begin
      E := B.Content (B.First);
      B.First := Storage_Index (((Integer (B.First) - 1 + 1) mod Max_Size) + 1);
      B.Length := B.Length - 1;
   end Pop;

end Ring_Buffer;
