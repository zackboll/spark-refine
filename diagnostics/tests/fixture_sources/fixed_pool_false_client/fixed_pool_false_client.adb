package body Fixed_Pool_False_Client with SPARK_Mode is

   procedure Initialize_Then_Claim_Empty is
      P : Pool;
   begin
      Initialize (P);
      --  Deliberately false: the proved postcondition of Initialize gives
      --  Free_Count (P) = Max_Objects.
      pragma Assert (Free_Count (P) = 0);
   end Initialize_Then_Claim_Empty;

end Fixed_Pool_False_Client;
