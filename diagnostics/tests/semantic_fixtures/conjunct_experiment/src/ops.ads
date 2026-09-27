package Ops with SPARK_Mode is

   procedure Op (X, Y : Integer)
   with Pre    => X > 0 and then Y > 0,
        Global => null;

   procedure Op3 (X, Y, Z : Integer)
   with Pre    => X > 0
                  and Y > 0
                  and Z > 0,
        Global => null;

   function F (X : Integer) return Integer
   with Pre    => X > 10 and then X < 1000,
        Post   => F'Result = X - 1,
        Global => null;

   --  Pre shapes for the extraction tests (Task 009)

   procedure No_Pre (X : Integer)
   with Global => null;

   procedure Paren_Or (X, Y : Integer)
   with Pre    => (X > 0 or else Y > 0) and then (X < 100),
        Global => null;

   procedure Nested_Calls (X : Integer)
   with Pre    => X in 12 .. 999 and then (F (F (X)) > 20 and X /= 500),
        Global => null;

   --  overloaded: resolved by argument type
   procedure Over (X : Integer)
   with Pre    => X > 0,
        Global => null;

   procedure Over (X : Boolean)
   with Pre    => X,
        Global => null;

end Ops;
