--  Task 014 experimental corpus: pre-registered caller states. Every
--  caller body is ONE call; the caller's own Pre sets up the state.
with Binding_Ops;    use Binding_Ops;
with Binding_Shapes; use Binding_Shapes;

package Binding_Client with SPARK_Mode is

   --  Family A: Map_Op (A > 0 and then B > 0 and then C > 0)
   procedure A1_Positional (X, Y, Z : Integer)
   with Pre => X > 0 and then Y > 0 and then Z > 0, Global => null;

   procedure A2_Named (X, Y, Z : Integer)
   with Pre => X > 0, Global => null;

   procedure A3_Reordered (X, Y, Z : Integer)
   with Pre => X > 0 and then Y > 0, Global => null;

   procedure A4_Reordered_Reversed (X, Y, Z : Integer)
   with Pre => Y > 0 and then Z > 0, Global => null;

   procedure A5_Defaulted (X : Integer)
   with Pre => X > 0, Global => null;

   procedure A6_Explicit_And_Default (X, Z : Integer)
   with Pre => X > 0, Global => null;

   procedure A7_Conversion (S : Long_Long_Integer; Y, Z : Integer)
   with Pre => S in 1 .. 1000 and then Y > 0, Global => null;

   procedure A8_Conversion_Unbounded (S : Long_Long_Integer; Y, Z : Integer)
   with Pre => S > 0 and then Y > 0 and then Z > 0, Global => null;

   --  Family B: Mutate (X > 0 and then Limit > X), X is in out
   procedure B1_In_Out (V : in out Integer; L : Integer)
   with Pre => V > 0 and then L > V, Global => null;

   procedure B2_In_Out_Named (V : in out Integer; L : Integer)
   with Pre => V > 0, Global => null;

   procedure B3_In_Out_Unconstrained (V : in out Integer; L : Integer)
   with Global => null;

   --  Family C: Above (Threshold > 0 and X > Threshold)
   procedure C1_Global (X : Integer)
   with Pre    => Threshold > 0 and then X > Threshold,
        Global => (Proof_In => Threshold);

   procedure C2_Global_Threshold_Only (X : Integer)
   with Pre    => Threshold > 0,
        Global => (Proof_In => Threshold);

   procedure C3_Global_Unconstrained (X : Integer)
   with Global => (Proof_In => Threshold);

   --  Family D: Check (Integer; Integer) / Check (Boolean; Integer)
   procedure D1_Int_Check (X, N : Integer)
   with Pre => X > 0 and then N > X, Global => null;

   procedure D2_Int_Check (X, N : Integer)
   with Pre => X > 0, Global => null;

   procedure D3_Int_Check (X, N : Integer)
   with Global => null;

   procedure D4_Bool_Check (B : Boolean; N : Integer)
   with Pre => B and then N > 0, Global => null;

   procedure D5_Bool_Check (B : Boolean; N : Integer)
   with Pre => B, Global => null;

   procedure D6_Bool_Check (B : Boolean; N : Integer)
   with Global => null;

   --  Family E: Binding_Int_Ops.Check (X > 0 and then X < 100)
   procedure E1_Generic (X : Integer)
   with Pre => X in 1 .. 99, Global => null;

   procedure E2_Generic (X : Integer)
   with Pre => X > 0, Global => null;

   procedure E3_Generic (X : Integer)
   with Global => null;

   --  Family F: dispatching Resize (Pre'Class N > 0 and then N < 100)
   procedure F1_Dispatch (S : Shape'Class; N : Integer)
   with Pre => N > 0 and then N < 100, Global => null;

   procedure F2_Dispatch (S : Shape'Class; N : Integer)
   with Pre => N > 0, Global => null;

   procedure F3_Dispatch (S : Shape'Class; N : Integer)
   with Global => null;

end Binding_Client;
