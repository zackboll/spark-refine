package Client with SPARK_Mode is

   procedure Second_Fails (X, Y : Integer)
   with Pre => X > 0, Global => null;

   procedure First_Fails (X, Y : Integer)
   with Pre => Y > 0, Global => null;

   procedure Both_Fail (X, Y : Integer)
   with Global => null;

   procedure Middle_Fails (X, Y, Z : Integer)
   with Pre => X > 0 and Z > 0, Global => null;

   procedure Shapes (X : Integer)
   with Global => null;

   procedure Shapes2 (X : Integer)
   with Global => null;

end Client;
