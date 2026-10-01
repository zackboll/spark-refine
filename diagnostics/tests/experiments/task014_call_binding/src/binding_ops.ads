--  Task 014 experimental corpus: callees whose Pre is reached through
--  non-trivial Ada actual/formal binding and callee selection.
package Binding_Ops with SPARK_Mode is

   --  Family A: named / reordered / defaulted / converted actuals
   procedure Map_Op
     (A : Integer;
      B : Integer := 1;
      C : Integer := 1)
   with Pre    => A > 0
                  and then B > 0
                  and then C > 0,
        Global => null;

   --  Family B: in out formal
   procedure Mutate
     (X     : in out Integer;
      Limit : Integer)
   with Pre    => X > 0
                  and then Limit > X,
        Global => null;

   --  Family C: package state read by the Pre
   Threshold : Integer := 10;

   procedure Above (X : Integer)
   with Pre    => Threshold > 0
                  and X > Threshold,
        Global => (Proof_In => Threshold);

   --  Family D: two overloads with the same source name
   procedure Check (X : Integer; N : Integer)
   with Pre    => X > 0
                  and N > X,
        Global => null;

   procedure Check (X : Boolean; N : Integer)
   with Pre    => X
                  and then N > 0,
        Global => null;

end Binding_Ops;
