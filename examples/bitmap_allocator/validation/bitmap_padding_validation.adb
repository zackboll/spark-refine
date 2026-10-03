package body Bitmap_Padding_Validation with SPARK_Mode is
   procedure Check (Words : Word_Array) is
   begin
      pragma Assert
        (Bitmap.Padding_Is_Canonical (Words)
          = ((Words (2) and not Interfaces.Unsigned_32 (2 ** 6 - 1)) = 0));
   end Check;
end Bitmap_Padding_Validation;