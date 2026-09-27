with SPARK.Containers.Functional.Sets;
with SPARK_Refine_Prefix_Sets;
with Prefix_Set_Obligations;

--  Validation instance 1 (extreme small): a one-identity universe whose only
--  value is 7 (lower bound /= 1), stored in a single storage position.
package Validate_Capacity_1 with SPARK_Mode is

   type Id is range 7 .. 7;
   type Slot is range 1 .. 1;
   type Store is array (Slot) of Id;

   package Id_Sets is new SPARK.Containers.Functional.Sets (Id);

   package PS is new SPARK_Refine_Prefix_Sets
     (Element_Type  => Id,
      Index_Type    => Slot,
      Storage_Array => Store,
      Element_Sets  => Id_Sets);

   package Obligations is new Prefix_Set_Obligations (PS);

end Validate_Capacity_1;
