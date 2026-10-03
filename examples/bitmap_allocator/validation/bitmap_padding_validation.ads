with Interfaces;
with SPARK.Containers.Functional.Sets;
with SPARK_Refine_Bitmap_Sets;

--  Independent raw-storage equivalence evidence, never used by the allocator.
package Bitmap_Padding_Validation with SPARK_Mode is
   subtype Object_Id is Natural range 0 .. 69;
   subtype Word_Index is Natural range 0 .. 2;
   type Word_Array is array (Word_Index) of Interfaces.Unsigned_32;
   package Id_Sets is new SPARK.Containers.Functional.Sets
     (Element_Type => Object_Id);
   package Bitmap is new SPARK_Refine_Bitmap_Sets
     (Object_Id, Interfaces.Unsigned_32, Word_Index, Word_Array, Id_Sets, 32);
   use type Interfaces.Unsigned_32;
   procedure Check (Words : Word_Array)
   with Ghost, Global => null,
        Post => Bitmap.Padding_Is_Canonical (Words)
          = ((Words (2) and not Interfaces.Unsigned_32 (2 ** 6 - 1)) = 0);
end Bitmap_Padding_Validation;