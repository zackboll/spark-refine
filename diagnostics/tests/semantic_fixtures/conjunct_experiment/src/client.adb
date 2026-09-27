with Ops;

package body Client with SPARK_Mode is

   procedure Second_Fails (X, Y : Integer) is
   begin
      Ops.Op (X, Y);
   end Second_Fails;

   procedure First_Fails (X, Y : Integer) is
   begin
      Ops.Op (X, Y);
   end First_Fails;

   procedure Both_Fail (X, Y : Integer) is
   begin
      Ops.Op (X, Y);
   end Both_Fail;

   procedure Middle_Fails (X, Y, Z : Integer) is
   begin
      Ops.Op3 (X, Y, Z);
   end Middle_Fails;

   procedure Shapes (X : Integer) is
      use Ops;
      V : Integer;
   begin
      Op (X,
          1);
      V := F (F (X)); Op (V, X);
      pragma Assert (V > 0);
   end Shapes;

   procedure Shapes2 (X : Integer) is
   begin
      Ops.No_Pre (X);
      Ops.Paren_Or (X, X);
      Ops.Nested_Calls (X);
      Ops.Over (X);
      Ops.Over (X > 0);
   end Shapes2;

end Client;
