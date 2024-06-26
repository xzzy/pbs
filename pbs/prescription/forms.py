from django import forms
from django.contrib.admin import widgets
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from pbs.prescription.models import (
    Prescription, Endorsement, BriefingChecklist,
    Approval, EndorsingRole, FundingAllocation, District)

from pbs.prescription.fields import LocationMultiField
from pbs.forms import PbsModelForm
from pbs.widgets import NullBooleanSelect
from django.utils import timezone


class UserChoiceField(forms.ModelChoiceField):
    '''Optional field override to disply users in a nicer fashion.
    '''
    def __init__(self, *args, **kwargs):
        kwargs['queryset'] = User.objects.filter(
            is_active=True).order_by('username')
        super(UserChoiceField, self).__init__(*args, **kwargs)

    def label_from_instance(self, obj):
        if obj.get_full_name():
            return obj.get_full_name()
        else:
            return obj.username


class PrescriptionFormBase(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super(PrescriptionFormBase, self).__init__(*args, **kwargs)
        if 'contentious' in self.fields:
            contentious = self.fields['contentious']
            contentious.choices = contentious.choices[1:]

        if 'planned_season' in self.fields:
            #self.fields['planned_season'].widget.attrs.update({'disabled':'disabled', 'readonly':True})
            self.fields['planned_season'].widget.attrs.update({'readonly':True})

    def clean_non_calm_tenure(self):
        value = self.cleaned_data.get("non_calm_tenure")
        if value is None:
            if self.instance and self.instance.planning_status != Prescription.PLANNING_DRAFT:
                raise forms.ValidationError("Must be either Yes or No")
        return value

    def clean_non_calm_tenure_included(self):
        if self.cleaned_data.get("non_calm_tenure"):
            value = self.cleaned_data.get("non_calm_tenure_included")
            if value:
                return value
            else:
                raise forms.ValidationError("Required.")
        else:
            return None

    def clean_non_calm_tenure_approved(self):
        if self.cleaned_data.get("non_calm_tenure"):
            return self.instance.non_calm_tenure_approved
        else:
            return None

    def clean_non_calm_tenure_value(self):
        if self.cleaned_data.get("non_calm_tenure"):
            value = self.cleaned_data.get("non_calm_tenure_value")
            if value:
                return value
            else:
                raise forms.ValidationError("Required.")
        else:
            return None

    def clean_non_calm_tenure_complete(self):
        if self.cleaned_data.get("non_calm_tenure"):
            value = self.cleaned_data.get("non_calm_tenure_complete")
            if value is None:
                raise forms.ValidationError("Required.")
            else:
                return value
        else:
            return None

    def clean_non_calm_tenure_risks(self):
        if self.cleaned_data.get("non_calm_tenure"):
            value = self.cleaned_data.get("non_calm_tenure_risks")
            if value:
                return value
            else:
                raise forms.ValidationError("Required.")
        else:
            return None

    def clean(self):
        cleaned_data = super(PrescriptionFormBase, self).clean()

        district = cleaned_data.get('district')
        if district is not None and not district:
            self._errors["district"] = self.error_class(
                ['This field is required.'])
        
        return cleaned_data


class PrescriptionCreateForm(PrescriptionFormBase):
    location = LocationMultiField(required=False)

    def __init__(self, *args, **kwargs):
        super(PrescriptionCreateForm, self).__init__(*args, **kwargs)
        self.fields['purposes'].error_messages.update({
            'required': 'There must be at least one burn purpose.'
        })

    def clean_district(self):
        """
        Force the user to select a district.
        """
        data = self.cleaned_data['district']
        if data is None:
            raise forms.ValidationError("You must select a district")
        # FIXME: hack to raise a form validation error on creation.
        if data.archive_date:
            raise forms.ValidationError("You cannot select an archived District")
        return data

    class Meta:
        model = Prescription
        fields = ('planned_season', 'financial_year', 'name', 'description', 'region',
                  'district', 'last_year', 'last_season',
                  'last_season_unknown', 'contentious', 'last_year_unknown',
                  'forest_blocks', 'contentious_rationale', 'purposes',
                  'aircraft_burn', 'priority', 'area', 'treatment_percentage',
                  'perimeter', 'location', 'remote_sensing_priority')


class PrescriptionEditForm(PrescriptionFormBase):
    location = LocationMultiField(required=False)

    def __init__(self, *args, **kwargs):
        prescription = kwargs.get('instance')

        super(PrescriptionEditForm, self).__init__(*args, **kwargs)
        self.fields["non_calm_tenure_complete"].choices = Prescription.NON_CALM_TENURE_COMPLETE_CHOICES
        if self.instance and self.instance.planning_status != self.instance.PLANNING_DRAFT:
            self.fields["non_calm_tenure"].widget=NullBooleanSelect(none=None)

        if 'description' in self.fields:
            self.fields['description'].widget.attrs.update({
                # 'rows': 8,  # Ignored in Chrome??
                # 'cols': 80,
                'style': 'width: 905px'
            })

        if prescription is not None:
            # filter the shires by current region
            shires = self.fields['shires'].queryset
            self.fields['shires'].queryset = shires.filter(
                district__region=prescription.region)

        #if prescription.carried_over:
#        if 'district' in self.fields:
            #self.fields['region'].widget.attrs['readonly'] = True
            #self.fields['region'].widget.attrs['disabled'] = True
            #self.fields['district'].widget.attrs['readonly'] = True
#            self.fields['district'].widget.attrs['disabled'] = True

        if prescription.has_corporate_approval and prescription.is_endorsed:
            if 'last_season' in self.fields:
                self.fields['last_season'].widget.attrs['readonly'] = True
            if 'last_year' in self.fields:
                self.fields['last_year'].widget.attrs['readonly'] = True

    class Meta:
        model = Prescription
        widgets = {
            "non_calm_tenure":NullBooleanSelect(attrs={"autocomplete":"off"}),
            "non_calm_tenure_approved":forms.widgets.CheckboxInput(attrs={"disabled":True,"autocomplete":"off"}),
            "non_calm_tenure_complete":forms.widgets.RadioSelect(),
            "non_calm_tenure_included":forms.widgets.Textarea(attrs={"style":"width:90%;"}),
            "non_calm_tenure_value":forms.widgets.Textarea(attrs={"style":"width:90%;"}),
            "non_calm_tenure_risks":forms.widgets.Textarea(attrs={"style":"width:90%;"})
        }


class PrescriptionSummaryForm(forms.ModelForm):
    location = LocationMultiField(required=False)

    def __init__(self, *args, **kwargs):
        prescription = kwargs.get('instance')

        super(PrescriptionSummaryForm, self).__init__(*args, **kwargs)
        # Add classes to some fields for nicer widths.
        self.fields['name'].widget.attrs.update({'class': 'span5'})
        self.fields['bushfire_act_zone'].widget.attrs.update(
            {'class': 'span10'})
        self.fields['prohibited_period'].widget.attrs.update(
            {'class': 'span10'})
        self.fields['prescribing_officer'] = UserChoiceField(required=False)
        self.fields['purposes'].error_messages.update({
            'required': 'There must be at least one burn purpose.'
        })
        if prescription is not None:
            # filter the shires by current region
            shires = self.fields['shires'].queryset
            self.fields['shires'].queryset = shires.filter(
                district__region=prescription.region)
            # filter the forecast areas by current region
            forecast_areas = self.fields['forecast_areas'].queryset
            self.fields['forecast_areas'].queryset = forecast_areas.filter(
                districts__region=prescription.region).distinct()

    class Meta:
        model = Prescription
        fields = ('financial_year', 'last_year', 'last_season',
                  'last_season_unknown', 'last_year_unknown', 'name', 'description',
                  'contentious', 'aircraft_burn',
                  'remote_sensing_priority', 'treatment_percentage', 'area',
                  'perimeter', 'location', 'purposes', 'tenures',
                  'fuel_types', 'shires', 'bushfire_act_zone',
                  'forecast_areas', 'prohibited_period', 'prescribing_officer',
                  'short_code', 'contentious_rationale')


class PrescriptionIgnitionCompletedForm(PbsModelForm):

    def __init__(self, *args, **kwargs):
        super(PrescriptionIgnitionCompletedForm, self).__init__(*args, **kwargs)
        self.fields['ignition_completed_date'].widget = widgets.AdminDateWidget()
        self.fields['ignition_completed_date'].widget.attrs.update({'class': 'vDateField input-small'})

    class Meta:
        model = Prescription
        fields = ('ignition_completed_date', )


class PrescriptionPriorityForm(PbsModelForm):
    def clean(self):
        # a bit ugly, I know but we want to attach the error to the individual
        # fields even though it should be in .non_field_errors :(
        priority = self.cleaned_data.get('priority')
        rationale = self.cleaned_data.get('rationale')

        if rationale and priority == 0:
            e = ValidationError('Overall Priority must be set for this ' +
                                'burn as it has been given an overall ' +
                                'rationale.')
            self._errors['priority'] = self.error_class(e.messages)
            if 'priority' in self.cleaned_data:
                del self.cleaned_data['priority']

        if priority and not rationale:
            e = ValidationError('Overall rationale must be set for this ' +
                                'burn as it has been given an overall ' +
                                'priority.')
            self._errors['rationale'] = self.error_class(e.messages)
            if 'rationale' in self.cleaned_data:
                del self.cleaned_data['rationale']

        return self.cleaned_data

    class Meta:
        model = Prescription
        fields = ('priority', 'rationale')


class EndorsingRoleForm(forms.ModelForm):
    required_endorsing_roles = []

    def __init__(self, *args, **kwargs):
        self.required_endorsing_roles = []
        if 'instance' in kwargs:
            # Apply business rules to include roles required by level
            # of risk and aerial burns
            prescription = kwargs['instance']

            initial = kwargs.get('initial') or {}
            # take either the saved endorsing roles or initial (exclusive)
            initial_endorsing_roles = (
                prescription.endorsing_roles.count() and
                list(prescription.endorsing_roles.values_list("pk",
                                                              flat=True)) or
                initial.get('endorsing_roles')
            #) or []
            ) or [EndorsingRole.objects.get(name__iexact="Fire Management Services Branch")]

            maximum_risk = prescription.get_maximum_risk
            """
            if prescription.aircraft_burn:
                self.required_endorsing_roles.append(
                    EndorsingRole.objects.get(
                        name__iexact="FMS Branch Representative"))
            """
            if maximum_risk.final_risk_level == maximum_risk.LEVEL_MEDIUM:
                self.required_endorsing_roles.append(
                    EndorsingRole.objects.get(name__iexact="District Manager"))
            if maximum_risk.final_risk_level == maximum_risk.LEVEL_HIGH:
                self.required_endorsing_roles.append(
                    EndorsingRole.objects.get(name__iexact="Regional Manager"))

            for required_endorsing_role in self.required_endorsing_roles:
                if not required_endorsing_role.id in initial_endorsing_roles:
                    initial_endorsing_roles.append(required_endorsing_role.id)

            initial['endorsing_roles'] = initial_endorsing_roles
            kwargs['initial'] = initial
        super(EndorsingRoleForm, self).__init__(*args, **kwargs)
        self.fields['endorsing_roles'].error_messages = {
            'required': 'Please select at least one endorsing role (including '
                        'all the required endorsing roles).'}

    def clean_endorsing_roles(self):
        """
        Ensures the required endorsing officers are always selected.
        """
        missing_endorsing_roles = []
        endorsing_roles = self.cleaned_data['endorsing_roles']
        for role in self.required_endorsing_roles:
            if not role in endorsing_roles:
                missing_endorsing_roles.append(role)

        if len(missing_endorsing_roles) > 0:
            raise ValidationError("This ePFP requires that %s endorse(s) it." %
                                  " and ".join(str(role) for role
                                               in missing_endorsing_roles))
        else:
            return endorsing_roles

    class Meta:
        model = Prescription
        fields = ('endorsing_roles',)


class AddEndorsementForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        if kwargs.get('request') is not None:
            self.request = kwargs['request']
            del kwargs['request']
        super(AddEndorsementForm, self).__init__(*args, **kwargs)

    class Meta:
        model = Endorsement
        exclude = ('prescription', 'endorsed',)


class AddApprovalForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        if (kwargs.get('initial') is not None and
                kwargs['initial'].get('prescription') is not None and
                kwargs['initial'].get('valid_to') is None):
            prescription = kwargs['initial']['prescription']
            if prescription.planned_season_object is not None:
                planned_season = prescription.planned_season_object
                # PBS-1754 - approved until 12months from approval date
                #kwargs['initial']['valid_to'] = planned_season.end
                kwargs['initial']['valid_to'] = timezone.now() + timezone.timedelta(days=365)
        super(AddApprovalForm, self).__init__(*args, **kwargs)
        if (kwargs.get('initial') is not None and
                kwargs['initial'].get('prescription') is not None):
            self.fields['prescription'].widget = forms.HiddenInput()

    class Meta:
        model = Approval


class BriefingChecklistForm(forms.ModelForm):

    class Meta:
        model = BriefingChecklist
        exclude = ('action', )
        fields = ('prescription', 'smeac', 'title', 'notes', )

class ProportionField(forms.DecimalField):
    """
    A proportion is represented as percentage between 0 and 100.
    """

    def __init__(self):
        super(ProportionField, self).__init__(
            min_value=0, max_value=100, max_digits=5, decimal_places=2)

class FundingAllocationForm(forms.ModelForm):
    """
    Interim form for the Prescription pre_summary form.
    """

    def save(self):
        # import ipdb; ipdb.set_trace()
        _boom = 1 / 0
        super(FundingAllocationForm, self).save()

    def is_valid(self):
        # import ipdb; ipdb.set_trace()
        super(FundingAllocationForm, self).is_valid()

    def clean(self):
        # import ipdb; ipdb.set_trace()
        _boom = 1 / 0
        super(FundingAllocationForm, self).clean()
        prop = self.cleaned_data.get('proportion')
        if not (0 <= prop <= 100):
            raise ValidationError("FundingAllocationForm.clean - Value must be between 0 and 100")

    class Meta:
        model = FundingAllocation
        fields = ['prescription', 'allocation', 'proportion']

class FundingAllocationInlineFormSet(forms.models.BaseInlineFormSet):

    def __init__(self, prescription, *args, **kwargs):
        super(FundingAllocationInlineFormSet, self).__init__(*args, **kwargs)
        self.prescription = prescription
        # Note. This queryset code is duplicated in PrescriptionAdmin.pre_summary
        self.queryset = FundingAllocation.objects.filter(prescription=self.prescription)

    def clean(self):
        # import ipdb; ipdb.set_trace()
        super(FundingAllocationInlineFormSet, self).clean()
        total = 0
        for form in self.forms:
            # Does the form represent a new or existing fund allocation?
            form.clean()
            ### The overide for the clean method in FundingAllocationForm is not getting called.
            if form.cleaned_data.get('allocation') is None:
                raise ValidationError('The allocation codes must not be empty!')
            prop = form.cleaned_data.get('proportion')
            if prop is not None:
                total += prop
        if total != 100:
            msg = "Total proportion allocated must be 100%;  currently {:5.2f}%".format(total)
            raise ValidationError(msg, code="cross-form")

    def save(self):
        for form in self.forms:
            form.save()
        super(FundingAllocationInlineFormSet, self).save()
