--  Task 014 experimental corpus, Family F: the smallest tagged hierarchy
--  with a class-wide precondition on a primitive operation.
package Binding_Shapes with SPARK_Mode is
   pragma Elaborate_Body;

   type Shape is tagged record
      Size : Integer;
   end record;

   procedure Resize (S : Shape; N : Integer)
   with Pre'Class => N > 0
                     and then N < 100,
        Global    => null;

   type Square is new Shape with null record;

   overriding procedure Resize (S : Square; N : Integer)
   with Global => null;

end Binding_Shapes;
