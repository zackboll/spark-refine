with Guarded_Ops; use Guarded_Ops;

package body Guarded_Client with SPARK_Mode is

   procedure A1_Guard_And_Value (P : Int_Access) is
   begin
      Use_Access (P);
   end A1_Guard_And_Value;

   procedure A2_Guard_Only (P : Int_Access) is
   begin
      Use_Access (P);
   end A2_Guard_Only;

   procedure A3_No_Guard (P : Int_Access) is
   begin
      Use_Access (P);
   end A3_No_Guard;

   procedure B1_Range_And_Value (A : Int_Array; I : Integer) is
   begin
      Use_Index (A, I);
   end B1_Range_And_Value;

   procedure B2_Range_Only (A : Int_Array; I : Integer) is
   begin
      Use_Index (A, I);
   end B2_Range_Only;

   procedure B3_No_Range (A : Int_Array; I : Integer) is
   begin
      Use_Index (A, I);
   end B3_No_Range;

   procedure C1_Guard_And_Value (X : Integer) is
   begin
      Use_Nested (X);
   end C1_Guard_And_Value;

   procedure C2_Guard_Only (X : Integer) is
   begin
      Use_Nested (X);
   end C2_Guard_Only;

   procedure C3_No_Guard (X : Integer) is
   begin
      Use_Nested (X);
   end C3_No_Guard;

end Guarded_Client;
