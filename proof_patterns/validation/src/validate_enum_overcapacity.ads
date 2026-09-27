with SPARK.Containers.Functional.Sets;
with SPARK_Refine_Prefix_Sets;
with Prefix_Set_Obligations;

--  Validation instance 3 (enumeration, storage larger than universe): three
--  identities stored in five positions 10 .. 14. The finite-universe lemma
--  is the only reason a unique prefix cannot exceed 3 entries here.
package Validate_Enum_Overcapacity with SPARK_Mode is

   type Color is (Red, Green, Blue);
   type Slot is range 10 .. 14;
   type Store is array (Slot) of Color;

   package Color_Sets is new SPARK.Containers.Functional.Sets (Color);

   package PS is new SPARK_Refine_Prefix_Sets
     (Element_Type  => Color,
      Index_Type    => Slot,
      Storage_Array => Store,
      Element_Sets  => Color_Sets);

   package Obligations is new Prefix_Set_Obligations (PS);

end Validate_Enum_Overcapacity;
