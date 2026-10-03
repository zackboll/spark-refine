package body Bitmap_Allocator with SPARK_Mode is
   procedure Mapping_Bridge (Words : Word_Array; Id : Object_Id) is
   begin
      pragma Assert (Bitmap.Word_Index (Id) = Id / 32);
      pragma Assert (Bitmap.Mask (Id) = Mask (Id));
   end Mapping_Bridge;

   function Bitmap_Model (Words : Word_Array) return Id_Sets.Set is
      S : constant Id_Sets.Set := Bitmap.Model (Words);
   begin
      for Id in Object_Id loop
         Mapping_Bridge (Words, Id);
         pragma Loop_Invariant
           (for all J in Object_Id'First .. Id =>
              Bitmap.Bit_Is_Set (Words, J) = Bitmap_Contains (Words, J));
      end loop;
      return S;
   end Bitmap_Model;

   function Is_Free (P : Pool; Id : Object_Id) return Boolean is
     (Bitmap_Contains (P.Words, Id));

   function Free_Count (P : Pool) return Pool_Count is (P.Count);
   function Is_Exhausted (P : Pool) return Boolean is (P.Count = 0);

   function Free_Model (P : Pool) return Id_Sets.Set is
     (Bitmap_Model (P.Words));

   procedure Initialize (P : out Pool) is
   begin
      P := (Words => [0 => Interfaces.Unsigned_32'Last,
                     1 => Interfaces.Unsigned_32'Last,
                     2 => 2 ** 6 - 1],
            Count => Capacity);
   end Initialize;

   procedure Allocate (P : in out Pool; Id : out Object_Id) is
      Old_Words : constant Word_Array := P.Words with Ghost;
   begin
      Id := Object_Id'First;
      for Candidate in Object_Id loop
         pragma Loop_Invariant
           (for all J in Object_Id'First .. Candidate - 1 => not Bitmap_Contains (P.Words, J));
         if Is_Free (P, Candidate) then
            Id := Candidate;
            Mapping_Bridge (Old_Words, Id);
            P.Words (Natural (Id) / 32) :=
              P.Words (Natural (Id) / 32) and not Mask (Id);
            P.Count := P.Count - 1;
            pragma Assert (P.Words = (Old_Words with delta
              Bitmap.Word_Index (Id) => Old_Words (Bitmap.Word_Index (Id))
                and not Bitmap.Mask (Id)));
            Bitmap.Lemma_Clear_Bit (Old_Words, P.Words, Id);
            pragma Assert
              (for all J in Object_Id => Bitmap_Contains (P.Words, J)
                = (J /= Id and then Bitmap_Contains (Old_Words, J)));
            return;
         end if;
      end loop;
   end Allocate;

   procedure Release (P : in out Pool; Id : Object_Id) is
      Old_Words : constant Word_Array := P.Words with Ghost;
   begin
      Mapping_Bridge (Old_Words, Id);
      P.Words (Natural (Id) / 32) :=
        P.Words (Natural (Id) / 32) or Mask (Id);
      pragma Assert (P.Words = (Old_Words with delta
        Bitmap.Word_Index (Id) => Old_Words (Bitmap.Word_Index (Id))
          or Bitmap.Mask (Id)));
      Bitmap.Lemma_Set_Bit (Old_Words, P.Words, Id);
      P.Count := P.Count + 1;
   end Release;
end Bitmap_Allocator;