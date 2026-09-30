package body Guarded_Ops with SPARK_Mode is

   procedure Use_Access (P : Int_Access) is null;

   procedure Use_Index (A : Int_Array; I : Integer) is null;

   function F (X : Integer) return Integer is (X - 1);

   procedure Use_Nested (X : Integer) is null;

end Guarded_Ops;
