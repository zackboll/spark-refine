private with SPARK_Refine_Bitmap_Sets;
with Interfaces;
use type Interfaces.Unsigned_32;
with SPARK.Big_Integers; use SPARK.Big_Integers;
with SPARK.Containers.Functional.Sets;

package Bitmap_Allocator with SPARK_Mode is
   Capacity : constant := 70;
   subtype Object_Id is Natural range 0 .. Capacity - 1;
   subtype Pool_Count is Natural range 0 .. Capacity;
   package Id_Sets is new SPARK.Containers.Functional.Sets
     (Element_Type => Object_Id);
   use type Id_Sets.Set;

   type Pool is private;
   function Free_Model (P : Pool) return Id_Sets.Set with Ghost;
   function Is_Free (P : Pool; Id : Object_Id) return Boolean
   with Post => Is_Free'Result = Id_Sets.Contains (Free_Model (P), Id);
   function Free_Count (P : Pool) return Pool_Count
   with Post => To_Big_Integer (Free_Count'Result) = Id_Sets.Length (Free_Model (P));
   function Is_Exhausted (P : Pool) return Boolean
   with Post => Is_Exhausted'Result = (Id_Sets.Length (Free_Model (P)) = 0);
   procedure Initialize (P : out Pool)
   with Post => Free_Count (P) = Capacity
     and (for all Id in Object_Id => Id_Sets.Contains (Free_Model (P), Id));
   procedure Allocate (P : in out Pool; Id : out Object_Id)
   with Pre => not Is_Exhausted (P),
        Post => Id_Sets.Contains (Free_Model (P)'Old, Id)
        and Free_Model (P) = Id_Sets.Remove (Free_Model (P)'Old, Id);
   procedure Release (P : in out Pool; Id : Object_Id)
   with Pre => not Id_Sets.Contains (Free_Model (P), Id),
        Post => Free_Model (P) = Id_Sets.Add (Free_Model (P)'Old, Id);

private
   subtype Word_Index is Natural range 0 .. 2;
   type Word_Array is array (Word_Index) of Interfaces.Unsigned_32;
   function Mask (Id : Object_Id) return Interfaces.Unsigned_32 is
     (Interfaces.Shift_Left (Interfaces.Unsigned_32 (1), Id mod 32));
   function Bitmap_Contains (Words : Word_Array; Id : Object_Id) return Boolean is
     ((Words (Id / 32) and Mask (Id)) /= 0);
   package Bitmap is new SPARK_Refine_Bitmap_Sets
     (Object_Id, Interfaces.Unsigned_32, Word_Index, Word_Array, Id_Sets, 32);
   procedure Mapping_Bridge (Words : Word_Array; Id : Object_Id)
   with Ghost, Global => null,
        Post => Bitmap.Word_Index (Id) = Id / 32
          and Bitmap.Mask (Id) = Mask (Id)
          and Bitmap.Bit_Is_Set (Words, Id) = Bitmap_Contains (Words, Id);
   function Bitmap_Model (Words : Word_Array) return Id_Sets.Set
   with Ghost,
        Post => (for all Id in Object_Id =>
          Id_Sets.Contains (Bitmap_Model'Result, Id) = Bitmap_Contains (Words, Id))
          and ((Id_Sets.Length (Bitmap_Model'Result) = Capacity)
            = (for all Id in Object_Id => Bitmap_Contains (Words, Id)))
          and ((Id_Sets.Length (Bitmap_Model'Result) = 0)
            = (for all Id in Object_Id => not Bitmap_Contains (Words, Id)));
   type Pool is record
      Words : Word_Array := [others => 0];
      Count : Pool_Count := 0;
   end record
   with Type_Invariant =>
     Bitmap.Padding_Is_Canonical (Pool.Words)
     and To_Big_Integer (Pool.Count) = Id_Sets.Length (Bitmap_Model (Pool.Words));
end Bitmap_Allocator;