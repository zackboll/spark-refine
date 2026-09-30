--  Task 013 experimental corpus: pre-registered caller states.
with Guarded_Ops; use Guarded_Ops;

package Guarded_Client with SPARK_Mode is

   --  Case A: access / null guard
   procedure A1_Guard_And_Value (P : Int_Access)
   with Pre => P /= null and then P.all > 0, Global => null;

   procedure A2_Guard_Only (P : Int_Access)
   with Pre => P /= null, Global => null;

   procedure A3_No_Guard (P : Int_Access)
   with Global => null;

   --  Case B: array index guard
   procedure B1_Range_And_Value (A : Int_Array; I : Integer)
   with Pre => I in A'Range and then A (I) > 0, Global => null;

   procedure B2_Range_Only (A : Int_Array; I : Integer)
   with Pre => I in A'Range, Global => null;

   procedure B3_No_Range (A : Int_Array; I : Integer)
   with Global => null;

   --  Case C: nested calls with their own Pre
   procedure C1_Guard_And_Value (X : Integer)
   with Pre => X in 23 .. 999, Global => null;

   procedure C2_Guard_Only (X : Integer)
   with Pre => X in 12 .. 999, Global => null;

   procedure C3_No_Guard (X : Integer)
   with Global => null;

end Guarded_Client;
