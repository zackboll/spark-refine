--  Task 013 experimental corpus: callees whose later Pre conjunct is
--  guarded by an earlier `and then` conjunct.
package Guarded_Ops with SPARK_Mode is

   type Int_Access is access constant Integer;

   type Int_Array is array (Positive range <>) of Integer;

   --  Case A: access / null guard
   procedure Use_Access (P : Int_Access)
   with Pre    => P /= null
                  and then P.all > 0,
        Global => null;

   --  Case B: array index guard
   procedure Use_Index (A : Int_Array; I : Integer)
   with Pre    => I in A'Range
                  and then A (I) > 0,
        Global => null;

   --  Case C: nested calls with their own Pre
   function F (X : Integer) return Integer
   with Pre    => X > 10 and then X < 1000,
        Post   => F'Result = X - 1,
        Global => null;

   procedure Use_Nested (X : Integer)
   with Pre    => X in 12 .. 999
                  and then F (F (X)) > 20,
        Global => null;

end Guarded_Ops;
