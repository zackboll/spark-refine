with Binding_Int_Ops;

package body Binding_Client with SPARK_Mode is

   procedure A1_Positional (X, Y, Z : Integer) is
   begin
      Map_Op (X, Y, Z);
   end A1_Positional;

   procedure A2_Named (X, Y, Z : Integer) is
   begin
      Map_Op (A => X, B => Y, C => Z);
   end A2_Named;

   procedure A3_Reordered (X, Y, Z : Integer) is
   begin
      Map_Op (C => Z, A => X, B => Y);
   end A3_Reordered;

   procedure A4_Reordered_Reversed (X, Y, Z : Integer) is
   begin
      Map_Op (C => Z, B => Y, A => X);
   end A4_Reordered_Reversed;

   procedure A5_Defaulted (X : Integer) is
   begin
      Map_Op (A => X);
   end A5_Defaulted;

   procedure A6_Explicit_And_Default (X, Z : Integer) is
   begin
      Map_Op (X, C => Z);
   end A6_Explicit_And_Default;

   procedure A7_Conversion (S : Long_Long_Integer; Y, Z : Integer) is
   begin
      Map_Op (A => Integer (S), B => Y, C => Z);
   end A7_Conversion;

   procedure A8_Conversion_Unbounded (S : Long_Long_Integer; Y, Z : Integer)
   is
   begin
      Map_Op (A => Integer (S), B => Y, C => Z);
   end A8_Conversion_Unbounded;

   procedure B1_In_Out (V : in out Integer; L : Integer) is
   begin
      Mutate (V, L);
   end B1_In_Out;

   procedure B2_In_Out_Named (V : in out Integer; L : Integer) is
   begin
      Mutate (Limit => L, X => V);
   end B2_In_Out_Named;

   procedure B3_In_Out_Unconstrained (V : in out Integer; L : Integer) is
   begin
      Mutate (X => V, Limit => L);
   end B3_In_Out_Unconstrained;

   procedure C1_Global (X : Integer) is
   begin
      Above (X);
   end C1_Global;

   procedure C2_Global_Threshold_Only (X : Integer) is
   begin
      Above (X => X);
   end C2_Global_Threshold_Only;

   procedure C3_Global_Unconstrained (X : Integer) is
   begin
      Above (X);
   end C3_Global_Unconstrained;

   procedure D1_Int_Check (X, N : Integer) is
   begin
      Check (X, N);
   end D1_Int_Check;

   procedure D2_Int_Check (X, N : Integer) is
   begin
      Check (N => N, X => X);
   end D2_Int_Check;

   procedure D3_Int_Check (X, N : Integer) is
   begin
      Check (X, N);
   end D3_Int_Check;

   procedure D4_Bool_Check (B : Boolean; N : Integer) is
   begin
      Check (B, N);
   end D4_Bool_Check;

   procedure D5_Bool_Check (B : Boolean; N : Integer) is
   begin
      Check (N => N, X => B);
   end D5_Bool_Check;

   procedure D6_Bool_Check (B : Boolean; N : Integer) is
   begin
      Check (B, N);
   end D6_Bool_Check;

   procedure E1_Generic (X : Integer) is
   begin
      Binding_Int_Ops.Check (X);
   end E1_Generic;

   procedure E2_Generic (X : Integer) is
   begin
      Binding_Int_Ops.Check (X);
   end E2_Generic;

   procedure E3_Generic (X : Integer) is
   begin
      Binding_Int_Ops.Check (X);
   end E3_Generic;

   procedure F1_Dispatch (S : Shape'Class; N : Integer) is
   begin
      Resize (S, N);
   end F1_Dispatch;

   procedure F2_Dispatch (S : Shape'Class; N : Integer) is
   begin
      Resize (S, N);
   end F2_Dispatch;

   procedure F3_Dispatch (S : Shape'Class; N : Integer) is
   begin
      Resize (S, N);
   end F3_Dispatch;

end Binding_Client;
