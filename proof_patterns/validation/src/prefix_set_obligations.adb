package body Prefix_Set_Obligations with SPARK_Mode is

   ------------------
   -- Empty_Prefix --
   ------------------

   procedure Empty_Prefix (S : PS.Storage_Array) is null;

   ----------
   -- Push --
   ----------

   procedure Push
     (S : in out PS.Storage_Array;
      C : in out PS.Count_Type;
      E : PS.Element_Type) is
   begin
      C := C + 1;
      S (PS.Prefix_Last (C)) := E;
   end Push;

   ---------
   -- Pop --
   ---------

   procedure Pop
     (S : PS.Storage_Array;
      C : in out PS.Count_Type;
      E : out PS.Element_Type) is
   begin
      E := S (PS.Prefix_Last (C));
      C := C - 1;
   end Pop;

   ---------------------------
   -- Missing_Implies_Short --
   ---------------------------

   procedure Missing_Implies_Short
     (S : PS.Storage_Array;
      C : PS.Count_Type;
      E : PS.Element_Type)
   is
      M : constant PS.Element_Sets.Set := PS.Model (S, C) with Unreferenced;
   begin
      null;
   end Missing_Implies_Short;

   ------------------
   -- Set_Has_Room --
   ------------------

   procedure Set_Has_Room (S : PS.Element_Sets.Set; E : PS.Element_Type) is
   begin
      PS.Lemma_Can_Add (S, E);
   end Set_Has_Room;

end Prefix_Set_Obligations;
