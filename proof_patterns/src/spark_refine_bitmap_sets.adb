package body SPARK_Refine_Bitmap_Sets with SPARK_Mode is
   procedure Equal_Length (Left, Right : Element_Sets.Set) is
   begin
      pragma Assert
        (Element_Sets.Num_Overlaps (Left, Right) = Element_Sets.Length (Left));
   end Equal_Length;

   function Model (Words : Storage_Array) return Element_Sets.Set is
      Result : Element_Sets.Set;
   begin
      for E in Element_Type loop
         pragma Loop_Invariant
           (for all J in Element_Type => Element_Sets.Contains (Result, J)
             = (J < E and then Bit_Is_Set (Words, J)));
         pragma Loop_Invariant
           (Element_Sets.Length (Result) <= To_Big_Integer (Offset (E)));
         pragma Loop_Invariant
           ((Element_Sets.Length (Result) = To_Big_Integer (Offset (E)))
             = (for all J in Element_Type =>
                  (if J < E then Bit_Is_Set (Words, J))));
         if Bit_Is_Set (Words, E) then
            Result := Element_Sets.Add (Result, E);
         end if;
      end loop;
      return Result;
   end Model;

   procedure Lemma_Clear_Bit
     (Old_Words, New_Words : Storage_Array; E : Element_Type) is
   begin
      pragma Assert
        (for all J in Element_Type => Bit_Is_Set (New_Words, J)
          = (J /= E and then Bit_Is_Set (Old_Words, J)));
      Equal_Length (Model (New_Words), Element_Sets.Remove (Model (Old_Words), E));
   end Lemma_Clear_Bit;

   procedure Lemma_Set_Bit
     (Old_Words, New_Words : Storage_Array; E : Element_Type) is
   begin
      pragma Assert
        (for all J in Element_Type => Bit_Is_Set (New_Words, J)
          = (J = E or else Bit_Is_Set (Old_Words, J)));
      Equal_Length (Model (New_Words), Element_Sets.Add (Model (Old_Words), E));
   end Lemma_Set_Bit;
end SPARK_Refine_Bitmap_Sets;