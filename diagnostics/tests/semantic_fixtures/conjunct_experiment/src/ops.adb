package body Ops with SPARK_Mode is

   procedure Op (X, Y : Integer) is null;

   procedure Op3 (X, Y, Z : Integer) is null;

   function F (X : Integer) return Integer is (X - 1);

   procedure No_Pre (X : Integer) is null;

   procedure Paren_Or (X, Y : Integer) is null;

   procedure Nested_Calls (X : Integer) is null;

   procedure Over (X : Integer) is null;

   procedure Over (X : Boolean) is null;

end Ops;
