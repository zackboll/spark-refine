with SPARK.Containers.Functional.Sets;
with SPARK_Refine_Prefix_Sets;
with Prefix_Set_Obligations;

--  Validation instance 2 (larger, offset): 200 identities -50 .. 149
--  (negative lower bound), stored in a 0-based array of a distinct index
--  type (index type /= identity type).
package Validate_Offset_Large with SPARK_Mode is

   type Id is range -50 .. 149;
   type Slot is range 0 .. 199;
   type Store is array (Slot) of Id;

   package Id_Sets is new SPARK.Containers.Functional.Sets (Id);

   package PS is new SPARK_Refine_Prefix_Sets
     (Element_Type  => Id,
      Index_Type    => Slot,
      Storage_Array => Store,
      Element_Sets  => Id_Sets);

   package Obligations is new Prefix_Set_Obligations (PS);

end Validate_Offset_Large;
