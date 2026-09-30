package body Binding_Ops with SPARK_Mode is

   procedure Map_Op
     (A : Integer;
      B : Integer := 1;
      C : Integer := 1) is null;

   procedure Mutate
     (X     : in out Integer;
      Limit : Integer) is
   begin
      X := X - 1;
   end Mutate;

   procedure Above (X : Integer) is null;

   procedure Check (X : Integer; N : Integer) is null;

   procedure Check (X : Boolean; N : Integer) is null;

end Binding_Ops;
