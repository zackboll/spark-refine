package body Fixed_Pool_Client_Proof with SPARK_Mode is

   procedure Two_Allocations_Then_Release (A, B : out Object_Id) is
      P : Pool;
   begin
      Initialize (P);
      pragma Assert (Free_Count (P) = Max_Objects);

      Allocate (P, A);
      pragma Assert (Is_Allocated (P, A));

      Allocate (P, B);
      pragma Assert (A /= B);
      pragma Assert (Is_Allocated (P, A) and Is_Allocated (P, B));
      pragma Assert (Free_Count (P) = Max_Objects - 2);

      Release (P, A);
      pragma Assert (Is_Free (P, A));
      pragma Assert (Is_Allocated (P, B));
      pragma Assert (Free_Count (P) = Max_Objects - 1);
   end Two_Allocations_Then_Release;

   procedure Round_Trip (P : in out Pool) is
      A : Object_Id;
   begin
      Allocate (P, A);
      Release (P, A);
   end Round_Trip;

   procedure Release_Then_Allocate (P : in out Pool; Id : Object_Id) is
      X : Object_Id;
   begin
      Release (P, Id);
      pragma Assert (Is_Free (P, Id));
      Allocate (P, X);
      pragma Assert (Is_Allocated (P, X));
   end Release_Then_Allocate;

end Fixed_Pool_Client_Proof;
