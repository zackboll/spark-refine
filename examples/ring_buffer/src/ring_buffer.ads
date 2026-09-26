package Ring_Buffer with SPARK_Mode is
   Max_Size : constant := 16;

   subtype Element is Integer;
   type Model_Array is array (Positive range <>) of Element;

   type Buffer is private;

   function Model (B : Buffer) return Model_Array with Ghost;

   function Is_Empty (B : Buffer) return Boolean;
   function Is_Full  (B : Buffer) return Boolean;

   procedure Push (B : in out Buffer; E : Element)
     with Pre  => not Is_Full (B),
          Post => Model (B) = Model (B)'Old & E;

   procedure Pop (B : in out Buffer; E : out Element)
     with Pre  => not Is_Empty (B),
          Post => E = Model (B)'Old (Model (B)'Old'First)
                  and then Model (B)'Length + 1 = Model (B)'Old'Length;

private
   subtype Storage_Index is Positive range 1 .. Max_Size;
   subtype Buffer_Length is Natural range 0 .. Max_Size;
   type Storage_Array is array (Storage_Index) of Element;

   type Buffer is record
      Content : Storage_Array := [others => 0];
      First   : Storage_Index := Storage_Index'First;
      Length  : Buffer_Length := 0;
   end record;
end Ring_Buffer;
