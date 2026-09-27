package body Ring_Buffer_Client_Proof with SPARK_Mode is

   procedure Push_Push_Pop (A, B : Element; X : out Element) is
      Q : Buffer;
   begin
      Initialize (Q);
      pragma Assert (Is_Empty (Q));

      Push (Q, A);
      Push (Q, B);
      Pop (Q, X);

      pragma Assert (X = A);
      pragma Assert (X /= B);
      pragma Assert (Model (Q) = [B]);
      pragma Assert (not Is_Empty (Q) and not Is_Full (Q));
   end Push_Push_Pop;

   procedure Rotate (Q : in out Buffer) is
      Head, X : Element;
   begin
      Peek (Q, Head);
      Pop (Q, X);
      pragma Assert (X = Head);
      Push (Q, X);
   end Rotate;

end Ring_Buffer_Client_Proof;
