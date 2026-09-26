with SPARK.Containers.Functional.Vectors;

package Ring_Buffer with SPARK_Mode is
   Max_Size : constant := 16;

   subtype Element is Integer;

   --  Abstract model: a finite mathematical sequence of elements, indexed
   --  from 1. It is used only from ghost code and contracts (Model is ghost).
   --  In the default build contracts and ghost code are disabled, so no
   --  sequence is ever constructed at run time; the instantiation itself
   --  cannot be marked Ghost (GNAT 16 rejects the aspect on instantiations).
   package Sequences is new SPARK.Containers.Functional.Vectors
     (Index_Type   => Positive,
      Element_Type => Element);
   use type Sequences.Sequence;

   type Buffer is private;

   function Model (B : Buffer) return Sequences.Sequence
   with Ghost,
        Post => Sequences.Last (Model'Result) <= Max_Size;
   --  The queue is bounded: its abstract contents never exceed Max_Size.

   function Is_Empty (B : Buffer) return Boolean
   with Post => Is_Empty'Result = (Sequences.Last (Model (B)) = 0);

   function Is_Full (B : Buffer) return Boolean
   with Post => Is_Full'Result = (Sequences.Last (Model (B)) = Max_Size);

   procedure Initialize (B : out Buffer)
   with Post => Model (B) = Sequences.Empty_Sequence;

   procedure Clear (B : in out Buffer)
   with Post => Model (B) = Sequences.Empty_Sequence;

   procedure Push (B : in out Buffer; E : Element)
   with Pre  => not Is_Full (B),
        Post => Model (B) = Sequences.Add (Model (B)'Old, E);

   procedure Pop (B : in out Buffer; E : out Element)
   with Pre  => not Is_Empty (B),
        Post => E = Sequences.Get (Model (B)'Old, 1)
                and Model (B) = Sequences.Remove (Model (B)'Old, 1);

   procedure Peek (B : Buffer; E : out Element)
   with Pre  => not Is_Empty (B),
        Post => E = Sequences.Get (Model (B), 1);

private
   subtype Storage_Index is Positive range 1 .. Max_Size;
   subtype Buffer_Length is Natural range 0 .. Max_Size;
   type Storage_Array is array (Storage_Index) of Element;

   type Buffer is record
      Content : Storage_Array := [others => 0];
      First   : Storage_Index := Storage_Index'First;
      Length  : Buffer_Length := 0;
   end record;

   --  Physical slot holding the logical element at zero-based Offset from
   --  First. Used by the production code (Push, Pop) and by the model.
   function Physical_Index
     (First : Storage_Index; Offset : Buffer_Length) return Storage_Index
   is (Storage_Index (((Natural (First) - 1) + Offset) mod Max_Size + 1));

end Ring_Buffer;
