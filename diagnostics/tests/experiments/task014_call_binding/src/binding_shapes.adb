package body Binding_Shapes with SPARK_Mode is

   procedure Resize (S : Shape; N : Integer) is null;

   overriding procedure Resize (S : Square; N : Integer) is null;

end Binding_Shapes;
